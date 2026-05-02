from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

Severity = Literal["info", "warning", "scam_strong"]
Locale = Literal["india", "us", "global"]

_RULES_PATH = Path(__file__).resolve().parent / "rules.yaml"


@dataclass(frozen=True)
class Rule:
    id: str
    severity: Severity
    pattern: re.Pattern[str]
    description: str
    applies_to: Locale


@dataclass(frozen=True)
class RuleHit:
    id: str
    severity: Severity
    description: str
    matched_text: str


@lru_cache(maxsize=1)
def load_rules(path: Path | None = None) -> list[Rule]:
    """Load rules from rules.yaml. Cached after first call.

    Mtime-based invalidation could be added later if hot-reload becomes
    important; for now the rules library is rarely edited and a process
    restart is cheap.
    """
    p = path or _RULES_PATH
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    rules: list[Rule] = []
    for r in raw.get("rules", []):
        rules.append(
            Rule(
                id=r["id"],
                severity=r["severity"],
                pattern=re.compile(r["pattern"], re.IGNORECASE),
                description=r["description"],
                applies_to=r.get("applies_to", "global"),
            )
        )
    return rules


def evaluate_text(
    text: str,
    *,
    locale: Locale = "global",
    rules: list[Rule] | None = None,
) -> list[RuleHit]:
    """Run all rules whose `applies_to` matches `locale` (or `global`)."""
    if not text:
        return []
    rules = rules if rules is not None else load_rules()
    hits: list[RuleHit] = []
    for rule in rules:
        if rule.applies_to != "global" and rule.applies_to != locale:
            continue
        match = rule.pattern.search(text)
        if match:
            hits.append(
                RuleHit(
                    id=rule.id,
                    severity=rule.severity,
                    description=rule.description,
                    matched_text=text[max(match.start() - 20, 0) : match.end() + 20],
                )
            )
    return hits


def static_check_score(hits: list[RuleHit]) -> int:
    """Compose a 0-100 score from rule hits. Lower = more concerning."""
    score = 100
    for h in hits:
        if h.severity == "scam_strong":
            score -= 40
        elif h.severity == "warning":
            score -= 15
        elif h.severity == "info":
            score -= 5
    return max(score, 0)

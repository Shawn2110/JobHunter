from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger("app.ai.truthfulness_check")


@dataclass
class TruthfulnessReport:
    passed: bool
    new_companies: list[str] = field(default_factory=list)
    new_titles: list[tuple[str, str]] = field(default_factory=list)
    changed_dates: list[dict[str, Any]] = field(default_factory=list)
    new_education: list[str] = field(default_factory=list)
    unsupported_skills: list[str] = field(default_factory=list)

    @property
    def violations(self) -> list[str]:
        msgs: list[str] = []
        for c in self.new_companies:
            msgs.append(f"Output adds company {c!r} not in source")
        for company, title in self.new_titles:
            msgs.append(f"Output adds title {title!r} for {company!r} not in source")
        for d in self.changed_dates:
            msgs.append(
                f"Output changes dates for {d['company']!r}: "
                f"{d['source_dates']!r} → {d['output_dates']!r}"
            )
        for e in self.new_education:
            msgs.append(f"Output adds education {e!r} not in source")
        for s in self.unsupported_skills:
            msgs.append(f"Output adds skill {s!r} not supported by source")
        return msgs


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _allowed_skills_universe(
    source_resume: dict[str, Any],
    brief: dict[str, Any] | None,
) -> set[str]:
    """All skills the output is allowed to claim:

    1. Skills explicitly listed in source.skills.
    2. Words that appear anywhere in source bullets (broad, defensible).
    3. Brief.keywords_truthfully_supported entries with a `source`.
    """
    universe: set[str] = set()

    for s in source_resume.get("skills") or []:
        if s:
            universe.add(_norm(s))

    bullet_text_parts: list[str] = []
    for exp in source_resume.get("experience") or []:
        for b in exp.get("bullets") or []:
            bullet_text_parts.append(b.lower())
    for proj in source_resume.get("projects") or []:
        if proj.get("description"):
            bullet_text_parts.append(proj["description"].lower())
        for t in proj.get("tech") or []:
            universe.add(_norm(t))
    summary = source_resume.get("summary")
    if summary:
        bullet_text_parts.append(summary.lower())
    bullet_text = " ".join(bullet_text_parts)

    if brief:
        for entry in brief.get("keywords_truthfully_supported") or []:
            kw = entry.get("keyword") if isinstance(entry, dict) else entry
            if kw:
                universe.add(_norm(kw))

    return universe, bullet_text


def check_truthfulness(
    *,
    source_resume: dict[str, Any],
    output_resume: dict[str, Any],
    brief: dict[str, Any] | None = None,
) -> TruthfulnessReport:
    """Validate that the rewritten resume invents nothing.

    Per Agent.md § Truthfulness Discipline + Critical Do-Not-Break tests.
    """
    report = TruthfulnessReport(passed=True)

    src_companies = {_norm(e.get("company")) for e in source_resume.get("experience") or []}
    src_titles_by_company: dict[str, set[str]] = {}
    src_dates_by_company: dict[str, tuple[str | None, str | None]] = {}
    for e in source_resume.get("experience") or []:
        company = _norm(e.get("company"))
        src_titles_by_company.setdefault(company, set()).add(_norm(e.get("title")))
        src_dates_by_company[company] = (e.get("start_date"), e.get("end_date"))

    for e in output_resume.get("experience") or []:
        company = _norm(e.get("company"))
        if company not in src_companies:
            report.new_companies.append(e.get("company", ""))
            continue
        if _norm(e.get("title")) not in src_titles_by_company.get(company, set()):
            report.new_titles.append((e.get("company", ""), e.get("title", "")))
        src_start, src_end = src_dates_by_company.get(company, (None, None))
        if (
            (src_start and e.get("start_date") and e.get("start_date") != src_start)
            or (src_end is not None and e.get("end_date") != src_end)
        ):
            report.changed_dates.append({
                "company": e.get("company", ""),
                "source_dates": (src_start, src_end),
                "output_dates": (e.get("start_date"), e.get("end_date")),
            })

    src_edu = {
        (_norm(ed.get("institution")), _norm(ed.get("degree")))
        for ed in source_resume.get("education") or []
    }
    for ed in output_resume.get("education") or []:
        if (_norm(ed.get("institution")), _norm(ed.get("degree"))) not in src_edu:
            report.new_education.append(
                f"{ed.get('institution', '')} — {ed.get('degree', '')}"
            )

    universe, bullet_text = _allowed_skills_universe(source_resume, brief)
    for s in output_resume.get("skills") or []:
        ns = _norm(s)
        if not ns:
            continue
        if ns in universe:
            continue
        if ns in bullet_text:
            continue
        report.unsupported_skills.append(s)

    report.passed = not (
        report.new_companies
        or report.new_titles
        or report.changed_dates
        or report.new_education
        or report.unsupported_skills
    )

    if not report.passed:
        log.warning(
            "truthfulness.violation",
            new_companies=report.new_companies,
            new_titles=report.new_titles,
            unsupported_skills=report.unsupported_skills,
        )
    return report

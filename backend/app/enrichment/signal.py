from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

log = structlog.get_logger("app.enrichment.signal")

# Strict-but-not-paranoid email pattern. Won't catch every edge case
# (foo+bar@example.com is fine; 国内字符@example.com is not) but
# correctly rejects garbage and is good enough for "did we find an
# email on a public page" extraction.
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


@dataclass
class PublicSignal:
    summary_md: str
    discovered_emails: list[tuple[str, str]]  # (email, source_label)


async def fetch_public_page(url: str) -> str | None:
    """Fetch any public URL with a short timeout and a polite UA."""
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            headers={"User-Agent": "JobHunt/0.1 (self-hosted, local-only)"},
            follow_redirects=True,
        ) as client:
            res = await client.get(url)
            if res.status_code >= 400:
                return None
            return res.text
    except httpx.HTTPError as e:
        log.info("signal.fetch_failed", url=url, error=str(e))
        return None


def extract_emails(text: str | None) -> list[str]:
    if not text:
        return []
    seen: list[str] = []
    for m in _EMAIL_RE.finditer(text):
        e = m.group(0).lower()
        if e not in seen and not _looks_junk(e):
            seen.append(e)
    return seen


def _looks_junk(email: str) -> bool:
    junk = ("example.com", "yourcompany.com", "domain.com", "test.com")
    return any(email.endswith(j) for j in junk)


async def aggregate_company_signals(
    *,
    company: str,
    company_about_url: str | None,
    extra_urls: list[str] | None = None,
) -> PublicSignal:
    """Pull public signals for outreach personalization.

    Per Agent.md § Hard Refusals: only fetches URLs the user / system
    explicitly provides. No third-party data brokers, no email-finder
    services, no SMTP verification.

    Returns a one-paragraph briefing plus opportunistically-discovered
    emails (with source labels). Emails default to [] when nothing is
    found on the public pages.
    """
    parts: list[str] = []
    discovered_emails: list[tuple[str, str]] = []

    targets: list[tuple[str, str]] = []
    if company_about_url:
        targets.append((company_about_url, "company_about_page"))
    for u in extra_urls or []:
        targets.append((u, "extra_public_page"))

    for url, label in targets:
        text = await fetch_public_page(url)
        if not text:
            continue
        # Strip HTML tags for the summary; we don't need full
        # extraction for v1.
        plain = re.sub(r"<[^>]+>", " ", text)
        plain = re.sub(r"\s+", " ", plain).strip()
        snippet = plain[:400] + ("..." if len(plain) > 400 else "")
        parts.append(f"From {label}: {snippet}")
        for email in extract_emails(text):
            if email not in {e for e, _ in discovered_emails}:
                discovered_emails.append((email, label))

    summary = (
        "\n\n".join(parts)
        if parts
        else f"No public signals fetched for {company}. The user can supply additional URLs."
    )
    return PublicSignal(summary_md=summary, discovered_emails=discovered_emails)

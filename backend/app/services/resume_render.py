from __future__ import annotations

from typing import Any


def render_resume_markdown(resume: dict[str, Any]) -> str:
    """Render a parsed-resume JSON to a clean ATS-safe Markdown string.

    Single column, standard section headings, no tables — these are the
    non-negotiables from PRD § 3.5. DOCX/PDF rendering is a separate
    concern that wraps this output (lands as a follow-up; python-docx
    is currently blocked by Application Control on the dev machine
    used to build P4-T4 — see ADR for context).
    """
    parts: list[str] = []

    name = resume.get("name", "")
    if name:
        parts.append(f"# {name}")

    contact_bits: list[str] = []
    for key in ("email", "phone", "location"):
        v = resume.get(key)
        if v:
            contact_bits.append(str(v))
    for link in resume.get("links") or []:
        url = link.get("url")
        kind = link.get("kind", "link")
        if url:
            contact_bits.append(f"{kind}: {url}")
    if contact_bits:
        parts.append(" · ".join(contact_bits))
    parts.append("")

    if resume.get("summary"):
        parts.append("## Summary")
        parts.append(resume["summary"])
        parts.append("")

    if resume.get("experience"):
        parts.append("## Experience")
        for e in resume["experience"]:
            header = f"### {e.get('title', '')} — {e.get('company', '')}"
            parts.append(header)
            date_bits: list[str] = []
            if e.get("start_date") or e.get("end_date"):
                date_bits.append(f"{e.get('start_date', '')} – {e.get('end_date') or 'Present'}")
            if e.get("location"):
                date_bits.append(e["location"])
            if date_bits:
                parts.append(" · ".join(date_bits))
            for b in e.get("bullets") or []:
                parts.append(f"- {b}")
            parts.append("")

    if resume.get("education"):
        parts.append("## Education")
        for ed in resume["education"]:
            line = f"### {ed.get('degree', '')} — {ed.get('institution', '')}"
            parts.append(line)
            extras: list[str] = []
            if ed.get("field"):
                extras.append(ed["field"])
            if ed.get("start_date") or ed.get("end_date"):
                extras.append(f"{ed.get('start_date', '')} – {ed.get('end_date', '')}")
            if ed.get("gpa"):
                extras.append(f"GPA: {ed['gpa']}")
            if extras:
                parts.append(" · ".join(extras))
            parts.append("")

    if resume.get("skills"):
        parts.append("## Skills")
        parts.append(", ".join(resume["skills"]))
        parts.append("")

    if resume.get("projects"):
        parts.append("## Projects")
        for p in resume["projects"]:
            parts.append(f"### {p.get('name', '')}")
            if p.get("description"):
                parts.append(p["description"])
            if p.get("tech"):
                parts.append("_Tech: " + ", ".join(p["tech"]) + "_")
            if p.get("url"):
                parts.append(p["url"])
            parts.append("")

    return "\n".join(parts).rstrip() + "\n"

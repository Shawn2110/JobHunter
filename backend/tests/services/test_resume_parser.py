from __future__ import annotations

import io
import json
import zipfile
from html import escape
from pathlib import Path

import pytest

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.services.resume_parser import (
    ResumeParseError,
    extract_text,
    parse_resume,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"


_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _make_docx(text_lines: list[str]) -> bytes:
    """Build a minimal valid DOCX in-memory using only stdlib zipfile.

    Avoids python-docx (which depends on lxml) so the fixture works on
    machines where Windows Application Control blocks lxml's DLL.
    """
    paragraphs = "".join(
        f"<w:p><w:r><w:t>{escape(line)}</w:t></w:r></w:p>" for line in text_lines
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}</w:body>"
        "</w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", document_xml)
    return buf.getvalue()


# ─── extract_text ────────────────────────────────────────────────────────────


def test_extract_text_from_docx() -> None:
    content = _make_docx([
        "Shawn Alfonso",
        "Backend engineer",
        "Bengaluru, India",
        "Experience: Razorpay 2022-2024",
    ])
    text = extract_text(content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "resume.docx")
    assert "Shawn Alfonso" in text
    assert "Razorpay" in text


def test_extract_text_format_detected_from_extension() -> None:
    content = _make_docx(["Some content here"])
    # No mime type → falls back to extension
    text = extract_text(content, None, "x.docx")
    assert "Some content here" in text


def test_extract_text_unsupported_format_raises() -> None:
    with pytest.raises(ResumeParseError, match="Unsupported"):
        extract_text(b"plain text", "text/plain", "resume.txt")


# ─── parse_resume (with frozen_claude) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_resume_full_pipeline(
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Patch the frozen response to return valid resume JSON.
    fake_parsed = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": None,
        "location": "Bengaluru",
        "summary": "Backend engineer",
        "experience": [
            {
                "company": "Razorpay",
                "title": "Senior Engineer",
                "start_date": "Jan 2022",
                "end_date": None,
                "location": "Bengaluru",
                "bullets": ["Built payment APIs"],
            }
        ],
        "education": [
            {
                "institution": "BITS Pilani",
                "degree": "B.E.",
                "field": "Computer Science",
                "start_date": "2018",
                "end_date": "2022",
                "gpa": None,
            }
        ],
        "skills": ["Python", "Go", "PostgreSQL"],
        "projects": [],
        "links": [{"kind": "github", "url": "https://github.com/test"}],
    }
    monkeypatch.setattr(
        frozen_claude._fake_messages.response.content[0],  # type: ignore[attr-defined]
        "text",
        json.dumps(fake_parsed),
    )

    content = _make_docx([
        "Test User",
        "Senior Engineer at Razorpay",
        "B.E. Computer Science from BITS Pilani 2018-2022",
        "Skills: Python, Go, PostgreSQL",
        "github.com/test",
        "Experience building payment APIs that processed millions in revenue.",
    ])

    loader = PromptLoader(PROMPTS_DIR)
    raw_text, parsed = await parse_resume(
        content=content,
        mime_type=None,
        filename="resume.docx",
        claude=frozen_claude,
        loader=loader,
    )

    assert "Test User" in raw_text
    assert parsed == fake_parsed
    # Confirm the rendered prompt was actually sent to Claude
    sent = frozen_claude._fake_messages.calls[-1]  # type: ignore[attr-defined]
    assert "Test User" in sent["messages"][0]["content"]


@pytest.mark.asyncio
async def test_parse_resume_short_text_raises(
    frozen_claude: ClaudeClient,
) -> None:
    loader = PromptLoader(PROMPTS_DIR)
    content = _make_docx(["x"])  # extracted text will be < 50 chars
    with pytest.raises(ResumeParseError, match="implausibly short"):
        await parse_resume(
            content=content,
            mime_type=None,
            filename="resume.docx",
            claude=frozen_claude,
            loader=loader,
        )

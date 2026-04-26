from __future__ import annotations

import io
import json
import zipfile
from html import escape

import pytest
from httpx import AsyncClient

from app.ai.claude import ClaudeClient

# Re-use the same minimal-DOCX builder as test_resume_parser; duplicated
# here to keep tests independent.

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


# ─── /profile (GET, PUT) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_profile_returns_null_initially(api_client: AsyncClient) -> None:
    res = await api_client.get("/profile")
    assert res.status_code == 200
    assert res.json() is None


@pytest.mark.asyncio
async def test_put_profile_creates_then_updates(api_client: AsyncClient) -> None:
    create = await api_client.put(
        "/profile",
        json={
            "name": "Test User",
            "headline": "Backend engineer",
            "salary_floor": 4000000,
            "salary_currency": "INR",
            "handles": [
                {"kind": "github", "url": "https://github.com/test"},
            ],
        },
    )
    assert create.status_code == 200
    body = create.json()
    assert body["name"] == "Test User"
    assert len(body["handles"]) == 1
    assert body["handles"][0]["kind"] == "github"

    update = await api_client.put(
        "/profile",
        json={
            "name": "Test User",
            "headline": "Senior backend engineer",  # changed
            "handles": [],  # cleared
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["headline"] == "Senior backend engineer"
    assert body["handles"] == []
    # ID should be the same — single-row table, in-place update
    assert body["id"] == create.json()["id"]


# ─── /profile/resume (POST) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_resume_parses_and_persists(
    api_client: AsyncClient,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_parsed = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": None,
        "location": "Bengaluru",
        "summary": None,
        "experience": [
            {
                "company": "Acme",
                "title": "Engineer",
                "start_date": "2022",
                "end_date": None,
                "location": None,
                "bullets": ["Built things"],
            }
        ],
        "education": [
            {
                "institution": "X University",
                "degree": "BS",
                "field": "CS",
                "start_date": None,
                "end_date": None,
                "gpa": None,
            }
        ],
        "skills": ["Python"],
        "projects": [],
        "links": [],
    }
    monkeypatch.setattr(
        frozen_claude._fake_messages.response.content[0],  # type: ignore[attr-defined]
        "text",
        json.dumps(fake_parsed),
    )

    docx_bytes = _make_docx([
        "Test User",
        "Engineer at Acme since 2022",
        "BS in Computer Science from X University",
        "Skills include Python and various other technologies.",
    ])

    res = await api_client.post(
        "/profile/resume",
        files={
            "file": (
                "resume.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["version"] == 1
    assert body["is_master"] is True
    assert body["parsed_json"]["name"] == "Test User"
    assert body["source_file_path"] is not None


@pytest.mark.asyncio
async def test_upload_resume_rejects_unsupported_format(
    api_client: AsyncClient,
) -> None:
    res = await api_client.post(
        "/profile/resume",
        files={"file": ("resume.txt", b"plain text resume content here", "text/plain")},
    )
    assert res.status_code == 422
    assert "Unsupported" in res.json()["detail"]


@pytest.mark.asyncio
async def test_upload_resume_rejects_empty_file(api_client: AsyncClient) -> None:
    res = await api_client.post(
        "/profile/resume",
        files={"file": ("resume.docx", b"", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res.status_code == 400

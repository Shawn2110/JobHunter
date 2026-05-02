"""Per Agent.md § Critical Do-Not-Break Tests.

Fabrication detection MUST work. If these break, resume tailoring is
unsafe and the user could end up with a resume they can't honestly
defend in interviews.
"""

from __future__ import annotations

from app.ai.truthfulness_check import check_truthfulness


SOURCE = {
    "name": "Shawn",
    "experience": [
        {
            "company": "Razorpay",
            "title": "Senior Backend Engineer",
            "start_date": "Jan 2022",
            "end_date": "Present",
            "bullets": [
                "Built payment APIs in Python and FastAPI handling 10M+ requests/day",
                "Led migration from PostgreSQL 13 to 15 with zero downtime",
            ],
        },
        {
            "company": "Acme",
            "title": "Backend Engineer",
            "start_date": "2020",
            "end_date": "2022",
            "bullets": ["Built internal tools in Python and Django"],
        },
    ],
    "education": [
        {"institution": "BITS Pilani", "degree": "B.E.", "field": "CS"},
    ],
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "projects": [],
}


def test_clean_rewrite_passes() -> None:
    output = {
        **SOURCE,
        "experience": [
            {
                **SOURCE["experience"][0],
                "bullets": [
                    "Built payment APIs in Python + FastAPI processing 10M+ requests/day",
                    "Led PostgreSQL 13 → 15 migration with zero downtime",
                ],
            },
            SOURCE["experience"][1],
        ],
    }
    report = check_truthfulness(source_resume=SOURCE, output_resume=output)
    assert report.passed
    assert report.violations == []


def test_invented_company_fails() -> None:
    output = {
        **SOURCE,
        "experience": [
            *SOURCE["experience"],
            {
                "company": "Stripe",
                "title": "Engineer",
                "start_date": "2024",
                "end_date": "Present",
                "bullets": ["Built the thing"],
            },
        ],
    }
    report = check_truthfulness(source_resume=SOURCE, output_resume=output)
    assert not report.passed
    assert any("Stripe" in v for v in report.violations)


def test_invented_title_for_real_company_fails() -> None:
    output = {
        **SOURCE,
        "experience": [
            {
                **SOURCE["experience"][0],
                "title": "VP of Engineering",  # was Senior Backend Engineer
            },
            SOURCE["experience"][1],
        ],
    }
    report = check_truthfulness(source_resume=SOURCE, output_resume=output)
    assert not report.passed
    assert any("VP of Engineering" in v for v in report.violations)


def test_invented_education_fails() -> None:
    output = {
        **SOURCE,
        "education": [
            *SOURCE["education"],
            {"institution": "Stanford", "degree": "M.S."},
        ],
    }
    report = check_truthfulness(source_resume=SOURCE, output_resume=output)
    assert not report.passed
    assert any("Stanford" in v for v in report.violations)


def test_invented_skill_fails() -> None:
    output = {**SOURCE, "skills": [*SOURCE["skills"], "Kubernetes"]}
    report = check_truthfulness(source_resume=SOURCE, output_resume=output)
    assert not report.passed
    assert any("Kubernetes" in v for v in report.violations)


def test_skill_in_bullet_text_passes() -> None:
    """If a skill appears in source bullet text, the output may list
    it explicitly even if not in source.skills."""
    src = {**SOURCE, "skills": ["Python"]}  # no FastAPI in skills
    output = {**src, "skills": ["Python", "FastAPI"]}  # FastAPI is in bullets
    report = check_truthfulness(source_resume=src, output_resume=output)
    assert report.passed


def test_skill_approved_in_brief_passes() -> None:
    src = {**SOURCE, "skills": ["Python"]}
    output = {**src, "skills": ["Python", "GraphQL"]}
    brief = {
        "keywords_truthfully_supported": [
            {"keyword": "GraphQL", "source": "github.repo.alpha"},
        ]
    }
    report = check_truthfulness(source_resume=src, output_resume=output, brief=brief)
    assert report.passed


def test_changed_dates_fail() -> None:
    output = {
        **SOURCE,
        "experience": [
            {**SOURCE["experience"][0], "start_date": "Jan 2018"},  # was 2022
            SOURCE["experience"][1],
        ],
    }
    report = check_truthfulness(source_resume=SOURCE, output_resume=output)
    assert not report.passed
    assert any("dates" in v for v in report.violations)

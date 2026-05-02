from __future__ import annotations

import pytest

from app.discovery.ats_providers import detect_ats


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://boards.greenhouse.io/postman", ("greenhouse", "postman")),
        (
            "https://job-boards.greenhouse.io/stripe/jobs/12345",
            ("greenhouse", "stripe"),
        ),
        (
            "https://boards-api.greenhouse.io/v1/boards/postman/jobs",
            ("greenhouse", "postman"),
        ),
        ("https://jobs.lever.co/figma/abcd-1234", ("lever", "figma")),
        ("https://jobs.lever.co/spotify", ("lever", "spotify")),
        ("https://jobs.ashbyhq.com/anthropic", ("ashby", "anthropic")),
        ("https://jobs.ashbyhq.com/linear/some-job-id", ("ashby", "linear")),
        # Slug normalization: case-insensitive match, lowercased slug
        ("https://BOARDS.GREENHOUSE.IO/Postman", ("greenhouse", "postman")),
        # Negative cases
        ("https://razorpay.com/jobs", None),
        ("https://www.naukri.com/python-developer-jobs-in-bengaluru", None),
        ("not a url", None),
        ("", None),
    ],
)
def test_detect_ats(url: str, expected: tuple[str, str] | None) -> None:
    assert detect_ats(url) == expected

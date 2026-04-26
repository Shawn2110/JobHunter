from __future__ import annotations

import pytest

from app.discovery.ats import detect_ats_family


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://razorpay.myworkdayjobs.com/job/123", "workday"),
        ("https://boards.greenhouse.io/acme/jobs/789", "greenhouse"),
        ("https://jobs.lever.co/acme/abcd-efgh", "lever"),
        ("https://acme.icims.com/jobs/123/apply", "icims"),
        ("https://acme.taleo.net/careersection/2/jobdetail.ftl", "taleo"),
        ("https://jobs.smartrecruiters.com/Acme/123", "smartrecruiters"),
        ("https://jobs.ashbyhq.com/acme/abc", "ashby"),
        ("https://www.naukri.com/job-listings-foo", "naukri"),
        ("https://wellfound.com/jobs/123", "wellfound"),
        ("https://angel.co/company/x/jobs/y", "wellfound"),
        ("https://example.com/careers/foo", None),
        (None, None),
        ("not a url", None),
    ],
)
def test_detect_ats_family(url: str | None, expected: str | None) -> None:
    assert detect_ats_family(url) == expected

from __future__ import annotations

import pytest

from app.discovery.dedupe import (
    canonical_company,
    description_similarity,
    is_duplicate,
    normalize_title,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Razorpay", "razorpay"),
        ("Razorpay Software Pvt. Ltd.", "razorpay software"),
        ("Acme Inc", "acme"),
        ("Acme, Inc.", "acme"),
        ("Acme Corp.", "acme"),
        ("Acme  &   Co.", "acme"),
        ("X-LLC", "x llc"),  # strict suffix match — "-LLC" doesn't get stripped
    ],
)
def test_canonical_company(raw: str, expected: str) -> None:
    assert canonical_company(raw) == expected


def test_normalize_title() -> None:
    assert normalize_title("Senior Frontend Engineer") == "senior frontend engineer"
    assert normalize_title("Sr. Frontend Engineer (Remote)") == "sr frontend engineer remote"


def test_description_similarity_identical() -> None:
    assert description_similarity("hello world", "hello world") == 1.0


def test_description_similarity_both_empty() -> None:
    assert description_similarity(None, None) == 1.0
    assert description_similarity("", "") == 1.0


def test_description_similarity_one_empty_one_not() -> None:
    assert description_similarity("hello", None) == 0.0


def test_is_duplicate_true_for_same_role_minor_text_changes() -> None:
    assert is_duplicate(
        "Razorpay Pvt Ltd",
        "Senior Frontend Engineer",
        "Build payment dashboards used by 10M+ businesses. React+TS+GraphQL.",
        "Razorpay",
        "Senior Frontend Engineer",
        "Build payment dashboards used by 10M+ businesses. React, TS, GraphQL.",
    )


def test_is_duplicate_false_for_different_company() -> None:
    assert not is_duplicate(
        "Razorpay", "Senior Engineer", "abc",
        "Stripe", "Senior Engineer", "abc",
    )


def test_is_duplicate_false_for_different_title() -> None:
    assert not is_duplicate(
        "Razorpay", "Senior Engineer", "abc",
        "Razorpay", "Junior Engineer", "abc",
    )

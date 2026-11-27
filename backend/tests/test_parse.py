"""Parsing is deliberately simple. Each case here is a shape a real paste has
taken, kept as a fixture so a change in the rules is visible in the diff."""

from __future__ import annotations

from pathlib import Path

import pytest

from dabjob.parse import parse_job

FIXTURES = Path(__file__).parent / "fixtures" / "jd"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_chinese_posting_with_prefixed_fields() -> None:
    parsed = parse_job(_fixture("backend-zh.txt"))

    assert parsed.title == "后端开发工程师"
    assert parsed.company == "示例科技"
    assert parsed.city == "上海"
    assert parsed.salary_min == 25000
    assert parsed.salary_max == 40000
    assert parsed.salary_text == "25-40K"
    assert parsed.seniority == "3-5年"


def test_english_posting() -> None:
    parsed = parse_job(_fixture("platform-en.txt"))

    assert parsed.title == "Senior Platform Engineer"
    assert parsed.company == "Blue Harbor"
    assert parsed.city == "Remote"
    assert parsed.salary_min == 120000
    assert parsed.salary_max == 160000
    assert parsed.seniority == "senior"


def test_unlabelled_posting_still_yields_a_title() -> None:
    parsed = parse_job(_fixture("analyst-zh.txt"))

    assert parsed.title == "数据分析师"
    assert parsed.company is None
    assert parsed.city == "北京"
    assert parsed.salary_min is None
    assert parsed.seniority is None


@pytest.mark.parametrize(
    ("salary", "low", "high"),
    [
        ("25-40K·14薪", 25000, 40000),
        ("8k-12k", 8000, 12000),
        ("15千-20千", 15000, 20000),
        ("40-25K", 25000, 40000),  # reversed by the parser, not the user
    ],
)
def test_salary_shapes(salary: str, low: int, high: int) -> None:
    parsed = parse_job(f"工程师\n{salary}")

    assert (parsed.salary_min, parsed.salary_max) == (low, high)


def test_annual_salary_text_is_not_guessed() -> None:
    """A yearly figure in a monthly field would be a 12x error."""
    parsed = parse_job("工程师\n年薪 50 万")

    assert parsed.salary_min is None
    assert parsed.salary_max is None

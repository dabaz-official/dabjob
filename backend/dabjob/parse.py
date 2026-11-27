"""Field extraction from a pasted posting.

Deliberately heuristic and deliberately small: a regex that is wrong is a
regex a user can see and correct, because every parsed field is editable in
the UI. This is the rule path that must work with no model configured.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

CITY_NAMES: tuple[str, ...] = (
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "成都",
    "南京",
    "武汉",
    "西安",
    "苏州",
    "厦门",
    "长沙",
    "合肥",
    "重庆",
    "天津",
    "青岛",
    "大连",
    "郑州",
    "济南",
    "宁波",
    "无锡",
    "福州",
    "东莞",
    "佛山",
    "珠海",
    "香港",
    "新加坡",
    "Remote",
    "远程",
)

_TITLE_PREFIX = re.compile(r"^\s*(?:职位名称|岗位名称|岗位|职位|job\s*title)\s*[:：]\s*", re.I)
_COMPANY_PREFIX = re.compile(r"^\s*(?:公司名称|公司|企业|company)\s*[:：]\s*(.+)$", re.I)
_SALARY = re.compile(
    r"(?<!\d)(?P<min>\d{1,3}(?:\.\d+)?)\s*(?P<unit_min>[kK千])?\s*[-~—–至]\s*"
    r"(?P<max>\d{1,3}(?:\.\d+)?)\s*(?P<unit_max>[kK千])?(?!\d)"
)
_SALARY_UNITS = {"k": 1000, "K": 1000, "千": 1000}
_SENIORITY_CN = re.compile(r"(\d+)\s*[-~—–至]\s*(\d+)\s*年")
_SENIORITY_ANY = re.compile(r"(\d+)\s*年以上")
_SENIORITY_EN = re.compile(r"(?i)\b(junior|mid[- ]?level|senior|staff|principal|lead|intern)\b")

_NOISE_LINES = re.compile(r"^(?:公司简介|职位描述|岗位职责|任职要求|工作地点|薪资范围)\s*[:：]?$")


@dataclass(frozen=True)
class ParsedJob:
    title: str | None = None
    company: str | None = None
    city: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_text: str | None = None
    seniority: str | None = None


def parse_job(text: str) -> ParsedJob:
    lines = [line.strip() for line in text.splitlines()]
    meaningful = [line for line in lines if line and not _NOISE_LINES.match(line)]
    salary_low, salary_high, salary_label = _salary(text)

    return ParsedJob(
        title=_title(meaningful),
        company=_company(lines),
        city=_city(text),
        salary_min=salary_low,
        salary_max=salary_high,
        salary_text=salary_label,
        seniority=_seniority(text),
    )


def _title(lines: list[str]) -> str | None:
    if not lines:
        return None
    candidate = _TITLE_PREFIX.sub("", lines[0]).strip()
    if not candidate or len(candidate) > 120:
        return None
    return candidate


def _company(lines: list[str]) -> str | None:
    for line in lines:
        match = _COMPANY_PREFIX.match(line)
        if match:
            name = match.group(1).strip()
            if name:
                return name[:255]
    return None


def _city(text: str) -> str | None:
    for city in CITY_NAMES:
        if city in text:
            return city
    return None


def _salary(text: str) -> tuple[int | None, int | None, str | None]:
    match = _SALARY.search(text)
    unit = (match.group("unit_max") or match.group("unit_min")) if match else None
    # Without a unit "3-5" is an experience range, not a salary.
    if not match or not unit:
        return (None, None, None)

    multiplier = _SALARY_UNITS[unit]
    low = int(float(match.group("min")) * multiplier)
    high = int(float(match.group("max")) * multiplier)
    if low > high:
        low, high = high, low
    return (low, high, match.group(0).strip())


def _seniority(text: str) -> str | None:
    if match := _SENIORITY_CN.search(text):
        return f"{match.group(1)}-{match.group(2)}年"
    if match := _SENIORITY_ANY.search(text):
        return f"{match.group(1)}年以上"
    if "应届" in text:
        return "应届"
    if match := _SENIORITY_EN.search(text):
        return match.group(1).lower().replace(" ", "-")
    return None


def main() -> int:
    """``make parse-jd FILE=...``: show what the rules extract, and what the
    gate found, before anything is written."""
    if len(sys.argv) < 2:
        print("usage: python -m dabjob.parse FILE", file=sys.stderr)
        return 2

    from .gate import inspect

    text = Path(sys.argv[1]).read_text(encoding="utf-8-sig")
    gated = inspect(text)
    report = {**asdict(parse_job(gated.text)), "flags": list(gated.flags)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

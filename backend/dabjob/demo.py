"""The demo dataset.

Five invented postings, so the UI is never empty on a first run and so the
acceptance checks in M1 have something to render. Nothing here is a real
person, company, address or phone number; the names are made up on purpose.

Run with ``make demo``. It is idempotent: a second run inserts nothing.
"""

from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .config import Settings
from .db import build_engine, build_sessionmaker
from .models import Job

DEMO_JOBS: tuple[dict[str, Any], ...] = (
    {
        "platform": "boss",
        "external_id": "demo-boss-001",
        "title": "后端开发工程师",
        "company_name": "示例科技",
        "city": "上海",
        "salary_min": 25000,
        "salary_max": 40000,
        "salary_text": "25-40K·14薪",
        "seniority": "3-5年",
        "url": "https://example.com/jobs/demo-boss-001",
        "jd_text": (
            "负责公司核心业务的服务端接口设计与开发。\n"
            "要求：熟悉 Python 与 FastAPI，熟练使用 PostgreSQL，"
            "了解 Redis 与消息队列；有高并发接口优化经验者优先。\n"
            "团队规模 8 人，双休，支持远程。"
        ),
    },
    {
        "platform": "linkedin",
        "external_id": "demo-linkedin-002",
        "title": "Senior Frontend Engineer",
        "company_name": "Northwind Labs",
        "city": "Remote",
        "salary_min": 120000,
        "salary_max": 160000,
        "salary_text": "USD 120k-160k",
        "seniority": "senior",
        "url": "https://example.com/jobs/demo-linkedin-002",
        "jd_text": (
            "Build the dashboard our customers live in. You will own the "
            "React and TypeScript frontend, work directly with design, and "
            "keep the bundle small.\n"
            "Requirements: 5+ years with React, strong TypeScript, experience "
            "with accessibility and performance profiling. Vite and Tailwind "
            "are a plus."
        ),
    },
    {
        "platform": "boss",
        "external_id": "demo-boss-003",
        "title": "数据分析师",
        "company_name": "星尘网络",
        "city": "北京",
        "salary_min": 18000,
        "salary_max": 28000,
        "salary_text": "18-28K",
        "seniority": "1-3年",
        "url": "https://example.com/jobs/demo-boss-003",
        "jd_text": (
            "负责增长业务的指标体系搭建与日常分析。\n"
            "要求：熟练使用 SQL，能用 Python 做数据清洗与建模，"
            "熟悉 Tableau 或同类可视化工具；有 A/B 实验设计经验者优先。"
        ),
    },
    {
        "platform": "csv",
        "external_id": "demo-csv-004",
        "title": "Platform Engineer",
        "company_name": "Blue Harbor",
        "city": "深圳",
        "salary_min": 30000,
        "salary_max": 45000,
        "salary_text": "30-45K·13薪",
        "seniority": "3-5年",
        "url": None,
        "jd_text": (
            "Own the deployment platform behind a dozen services. "
            "Requirements: Kubernetes in production, Terraform, and enough "
            "Go or Python to write the tooling you are missing. On-call is "
            "one week in six."
        ),
    },
    {
        "platform": "paste",
        "external_id": "demo-paste-005",
        "title": "算法工程师（推荐方向）",
        "company_name": "青禾数据",
        "city": "杭州",
        "salary_min": 35000,
        "salary_max": 60000,
        "salary_text": "35-60K·16薪",
        "seniority": "3-5年",
        "url": None,
        "jd_text": (
            "负责推荐系统的召回与排序模型迭代。\n"
            "要求：熟悉 PyTorch，有推荐系统或搜索排序的落地经验，"
            "理解特征工程与线上 A/B 评估；发表过相关论文者优先。"
        ),
    },
)


def seed(session: Session) -> int:
    """Insert the demo postings that are not there yet. Returns how many."""
    inserted = 0
    for payload in DEMO_JOBS:
        existing = session.scalar(
            select(Job.id).where(
                Job.platform == payload["platform"],
                Job.external_id == payload["external_id"],
            )
        )
        if existing is None:
            session.add(Job(**payload))
            inserted += 1
    session.commit()
    return inserted


def main() -> int:
    settings = Settings()
    engine = build_engine(settings)

    try:
        with build_sessionmaker(engine)() as session:
            inserted = seed(session)
            total = session.scalar(select(func.count()).select_from(Job))
    except OperationalError as error:
        print(f"demo: the database is not migrated ({error.orig})", file=sys.stderr)
        print("demo: run `make migrate` first", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print(f"demo: inserted {inserted}, {total} posting(s) in the database")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

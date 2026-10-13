#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import duckdb


EXPORTS = {
    "annual_metrics.csv": """
        select *
        from mart.mart_tokyo_precipitation_annual_metrics
        order by year
    """,
    "daily_cumulative.csv": """
        select *
        from mart.mart_tokyo_precipitation_daily_cumulative
        order by observed_date
    """,
    "monthly_metrics.csv": """
        select *
        from mart.mart_tokyo_precipitation_monthly_metrics
        order by month_start
    """,
    "period_metrics.csv": """
        select *
        from mart.mart_tokyo_precipitation_period_metrics
        order by period_key, year
    """,
    "streaks.csv": """
        select *
        from int.int_tokyo_precipitation_streaks
        order by streak_start_date
    """,
}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    database = root / "tokyo_precipitation.duckdb"
    output_dir = root / "data" / "pages"

    if not database.exists():
        raise SystemExit(
            f"{database} が見つかりません。先に `uv run dbt build --project-dir dbt --profiles-dir dbt` "
            "を実行してください。"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(database), read_only=True)
    try:
        for filename, query in EXPORTS.items():
            destination = output_dir / filename
            connection.execute(
                f"copy ({query}) to '{destination}' with (header, delimiter ',')"
            )
            print(f"wrote {destination.relative_to(root)}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()

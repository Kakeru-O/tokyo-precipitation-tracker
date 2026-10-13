from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl


TABLES = {
    "annual": "mart.mart_tokyo_precipitation_annual_metrics",
    "daily": "mart.mart_tokyo_precipitation_daily_cumulative",
    "monthly": "mart.mart_tokyo_precipitation_monthly_metrics",
    "periods": "mart.mart_tokyo_precipitation_period_metrics",
    "streaks": "int.int_tokyo_precipitation_streaks",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def duckdb_path(root: Path | None = None) -> Path:
    return (root or project_root()) / "tokyo_precipitation.duckdb"


def query_polars(connection: duckdb.DuckDBPyConnection, sql: str) -> pl.DataFrame:
    result = connection.execute(sql)
    columns = [column[0] for column in result.description]
    return pl.DataFrame(result.fetchall(), schema=columns, orient="row")


def load_table(name: str, root: Path | None = None) -> pl.DataFrame:
    if name not in TABLES:
        raise ValueError(f"Unknown dashboard table: {name}")

    path = duckdb_path(root)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} が見つかりません。先に `uv run dbt build --project-dir dbt --profiles-dir dbt` "
            "を実行してください。"
        )

    schema, table = TABLES[name].split(".")
    connection = duckdb.connect(str(path), read_only=True)
    try:
        exists = connection.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = ? and table_name = ?
            limit 1
            """,
            [schema, table],
        ).fetchone()
        if not exists:
            raise RuntimeError(
                f"{TABLES[name]} が見つかりません。先に dbt build を実行してください。"
            )
        order_by = "year" if name == "annual" else {
            "daily": "observed_date",
            "monthly": "month_start",
            "periods": "period_key, year",
            "streaks": "streak_start_date",
        }[name]
        return query_polars(
            connection,
            f"select * from {TABLES[name]} order by {order_by}",
        )
    finally:
        connection.close()


def complete_years(frame: pl.DataFrame) -> pl.DataFrame:
    """Return years that are safe for annual rankings, averages, and comparisons."""
    return frame.filter(pl.col("is_complete_calendar_year"))


def period_slice(frame: pl.DataFrame, start_year: int, end_year: int) -> pl.DataFrame:
    lower, upper = sorted((start_year, end_year))
    return frame.filter(pl.col("year").is_between(lower, upper))


def format_number(value: object, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "-"
    return f"{float(value):,.{digits}f}{suffix}"


def difference(left: object, right: object, digits: int = 1) -> str:
    if left is None or right is None:
        return "-"
    return f"{float(right) - float(left):+,.{digits}f}"

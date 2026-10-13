#!/usr/bin/env python3
"""Normalize JMA multi-row precipitation CSVs without changing the raw files."""

from __future__ import annotations

import csv
from pathlib import Path

import polars as pl


RAW_COLUMNS = [
    "date",
    "precipitation_mm_raw",
    "phenomenon_none_code",
    "quality_code",
    "homogeneity_number",
]
EXPECTED_HEADER = [
    "年月日",
    "降水量の合計(mm)",
    "降水量の合計(mm)",
    "降水量の合計(mm)",
    "降水量の合計(mm)",
]
EXPECTED_DETAIL_HEADER = ["", "", "現象なし情報", "品質情報", "均質番号"]


def detect_encoding(path: Path) -> str:
    for encoding in ("cp932", "utf-8-sig"):
        try:
            path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        return encoding
    raise RuntimeError(f"CSVをCP932またはUTF-8として読み込めません: {path}")


def validate_header(path: Path, encoding: str) -> None:
    with path.open(encoding=encoding, newline="") as source:
        header = list(csv.reader(source))[:5]
    if len(header) != 5 or header[3] != EXPECTED_HEADER or header[4] != EXPECTED_DETAIL_HEADER:
        raise ValueError(f"未対応の気象庁CSVヘッダーです: {path}")


def load_raw_csv(path: Path) -> pl.DataFrame:
    encoding = detect_encoding(path)
    validate_header(path, encoding)
    polars_encoding = "shift_jis" if encoding == "cp932" else "utf8"
    frame = pl.read_csv(
        path,
        skip_rows=5,
        has_header=False,
        new_columns=RAW_COLUMNS,
        encoding=polars_encoding,
        schema_overrides={column: pl.String for column in RAW_COLUMNS},
        null_values=[""],
    )
    return frame.with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y/%m/%d", strict=True),
        pl.col("precipitation_mm_raw")
        .cast(pl.Float64, strict=False)
        .alias("precipitation_mm"),
        pl.col("phenomenon_none_code").cast(pl.Int8, strict=False),
        pl.col("quality_code").cast(pl.Int8, strict=False),
        pl.col("homogeneity_number").cast(pl.Int16, strict=False),
        pl.lit(path.name).alias("source_file"),
    ).select(
        "date",
        "precipitation_mm",
        "precipitation_mm_raw",
        "phenomenon_none_code",
        "quality_code",
        "homogeneity_number",
        "source_file",
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    raw_dir = root / "data" / "raw"
    processed_dir = root / "data" / "processed"
    raw_files = sorted(raw_dir.glob("jma_tokyo_precipitation_*.csv"))
    if not raw_files:
        raise SystemExit(f"raw CSVがありません: {raw_dir}")

    processed_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pl.DataFrame] = []
    for raw_path in raw_files:
        frame = load_raw_csv(raw_path)
        frames.append(frame)
        output_path = processed_dir / raw_path.name
        frame.write_csv(output_path, date_format="%Y-%m-%d")
        print(f"wrote {output_path.relative_to(root)} ({frame.height:,} rows)")

    combined = pl.concat(frames)
    duplicates = combined.group_by("date").len().filter(pl.col("len") > 1)
    if duplicates.height:
        raise RuntimeError(f"ファイル間で日付が重複しています:\n{duplicates}")
    print(
        "validated "
        f"{combined.height:,} unique dates: "
        f"{combined['date'].min()} through {combined['date'].max()}"
    )


if __name__ == "__main__":
    main()

# tokyo-precipitation-tracker

東京（北の丸公園、地点47662）の日別降水量を、気象庁CSVからDuckDB/dbtへ取り込むプロジェクトです。

この段階ではデータ基盤（前処理、`stg -> int -> mart`、品質テスト）を実装しています。marimo / Altairによる可視化は次段階です。

## Setup

```bash
uv sync
uv run python3 scripts/prepare_processed_jma.py
uv run dbt build --project-dir dbt --profiles-dir dbt
```

主要なmartは次の3つです。

- `mart.mart_tokyo_precipitation_annual_metrics`: 年間降水量、降水日数、降水強度、最長連続降水／無降水
- `mart.mart_tokyo_precipitation_daily_cumulative`: 日別値と年内累積
- `mart.mart_tokyo_precipitation_monthly_metrics`: 月別値

CSV仕様・品質コード・2026年の37日連続降水の検証は [docs/data.md](docs/data.md) を参照してください。dbtモデルの定義は [docs/dbt.md](docs/dbt.md) にあります。

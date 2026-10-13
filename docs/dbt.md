# dbtモデル

## レイヤー

- `stg_jma_tokyo_daily_precipitation`: 型変換、品質ラベル、現象なし情報のboolean化
- `int_tokyo_daily_precipitation_features`: 正常値フラグ、降水／無降水、年内累積
- `int_tokyo_precipitation_streaks`: 欠測・品質不良・日付欠落で分断する全期間streak
- `int_tokyo_monthly_precipitation`: 月別降水量・日数・強度・最大日量
- `int_tokyo_annual_precipitation`: 年別降水量・日数・強度・品質件数
- `mart_tokyo_precipitation_annual_metrics`: 年次値と年をまたぐ最長streak
- `mart_tokyo_precipitation_daily_cumulative`: 可視化向け日別累積
- `mart_tokyo_precipitation_monthly_metrics`: 可視化向け月別値

`annual_precipitation_mm`と月別`precipitation_mm`は品質8の値だけを合計する。`reported_precipitation_mm`は資料不足値を含む報告値の監査用合計である。年次モデルの`period_start_date`、`period_end_date`、`is_complete_calendar_year`で、2026年のような途中年と欠測を含む年を完全な暦年から区別する。

## テスト

```bash
uv run dbt build --project-dir dbt --profiles-dir dbt
```

日付一意性、コード値、値域、品質件数の整合、降水量と現象なし情報の矛盾、streak長と日付範囲の整合、2026年37日記録を検査する。

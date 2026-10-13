# dbtモデル

## レイヤー

- `stg_jma_tokyo_daily_precipitation`: 型変換、品質ラベル、現象なし情報のboolean化
- `int_tokyo_daily_precipitation_features`: 正常値フラグ、降水／無降水、年内累積
- `int_tokyo_precipitation_streaks`: 欠測・品質不良・日付欠落で分断する全期間streak
- `int_tokyo_monthly_precipitation`: 月別降水量・日数・強度・最大日量
- `int_tokyo_annual_precipitation`: 年別降水量・日数・強度・品質件数
- `mart_tokyo_precipitation_annual_metrics`: 年次値と、暦年境界で切り詰めた年間最長streak
- `mart_tokyo_precipitation_daily_cumulative`: 可視化向け日別累積
- `mart_tokyo_precipitation_monthly_metrics`: 可視化向け月別値
- `mart_tokyo_precipitation_period_metrics`: 年間・梅雨期（6〜7月）・台風期（8〜10月）の固定期間比較

`annual_precipitation_mm`と月別`precipitation_mm`は品質8の値だけを合計する。`reported_precipitation_mm`は資料不足値を含む報告値の監査用合計である。年次モデルの`period_start_date`、`period_end_date`、`is_complete_calendar_year`で、1月1日から12月31日まで正常な観測がそろった年と、2026年のような途中年・欠測を含む年を区別する。

主要指標の`mean_precipitation_per_precipitation_day_mm`は、期間降水量を`precipitation_days`（0.0mmの微量降水を含む降水現象日数）で割る。`mean_precipitation_per_measurable_day_mm`は、0.0mm超の日だけを分母にする補助指標として区別して保持する。固定期間martは期間の全日が存在し品質8で揃う場合だけ`is_complete_period=true`とするため、2026年の6〜7月は比較対象、8〜10月は10月12日時点の参考値として区別できる。

## テスト

```bash
uv run dbt build --project-dir dbt --profiles-dir dbt
```

日付一意性、コード値、値域、品質件数の整合、降水量と現象なし情報の矛盾、streak長と日付範囲の整合、2026年37日記録を検査する。

全期間のstreakは`int_tokyo_precipitation_streaks`で年をまたいだまま保持する。年次martでは各streakを1月1日〜12月31日に切り詰め、その年に含まれる日数と開始・終了日だけを年間記録として比較する。

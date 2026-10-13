# tokyo-precipitation-tracker

東京（北の丸公園、地点47662）の日別降水量を、気象庁CSVからDuckDB/dbtへ取り込み、marimo + Polars + Altairで可視化するプロジェクトです。

ローカル版はDuckDBのmartテーブルを直接読みます。GitHub Pages向けには、同じテーブルを事前出力したCSVをmarimo WebAssembly版が読み込みます。

## Stack

- marimo
- Polars
- Altair
- DuckDB
- dbt / dbt-duckdb

## Setup

```bash
uv sync
uv run python3 scripts/prepare_processed_jma.py
uv run dbt build --project-dir dbt --profiles-dir dbt
uv run marimo edit main.py
```

`main.py` では次を確認できます。

- 年間降水量と降水日数を重ねた長期推移と、クリックした年の詳細
- 選択年の日降水量・年内累計と、完全年の累積分布
- 年間降水量・降水日数・降水日の平均降水量・最大日降水量・年内最長連続降水のランキング
- 年間・梅雨期（6〜7月）・台風期（8〜10月）の固定期間比較

年間ランキングと長期平均には完全な暦年だけを使います。2026年や欠測を含む年は、年詳細と長期推移で観測済み期間を明示した参考値として表示します。

主要なmartは次の4つです。

- `mart.mart_tokyo_precipitation_annual_metrics`: 年間降水量、降水日数、降水強度、最長連続降水／無降水
- `mart.mart_tokyo_precipitation_daily_cumulative`: 日別値と年内累積
- `mart.mart_tokyo_precipitation_monthly_metrics`: 月別値
- `mart.mart_tokyo_precipitation_period_metrics`: 年間・6〜7月・8〜10月の固定期間指標と集計完了判定

CSV仕様・品質コード・2026年の37日連続降水の検証は [docs/data.md](docs/data.md) を参照してください。dbtモデルの定義は [docs/dbt.md](docs/dbt.md) にあります。

## GitHub Pages用CSV

Pagesではブラウザ上でdbt/DuckDBを実行しないため、mart/intテーブルをCSVへ書き出します。

```bash
uv run python3 scripts/export_pages_data.py
```

出力先は `data/pages/` です（生成物のためgit管理外）。次の公開フェーズでは、以下のようにWASM版HTMLとCSVを同じ公開ディレクトリへ配置できます。

```bash
uv run marimo export html-wasm main.py -o site --mode run --no-show-code
mkdir -p site/data/pages
cp data/pages/*.csv site/data/pages/
python3 -m http.server --directory site 8000
```

ブラウザで `http://localhost:8000` を開きます。このIssueでは公開ワークフロー自体は追加していません。

## 表示上の定義

- 降水日: 品質コード8かつ気象庁の現象なし情報が `0` の日。降水量が `0.0mm` でも微量降水現象があれば含みます。
- 降水日の平均降水量: 期間降水量を、品質コード8かつ降水量が `0.0mm` を超えた日数で割った値。
- 無降水日: 品質コード8かつ現象なし情報が `1` の日。
- 年内最長連続降水: 暦年の境界でクリップしたストリーク。全期間の年跨ぎストリークとは別に表示します。
- 累積平年帯: 完全年の日別累積降水量の25〜75%点。日降水量そのものの分布ではありません。

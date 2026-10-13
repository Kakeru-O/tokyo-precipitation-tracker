#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "altair>=6.3.0",
#     "duckdb>=1.5.6",
#     "marimo>=0.25.1",
#     "polars>=2.0.0",
# ]
# ///

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="full")


@app.cell
def _():
    import importlib
    import io
    import sys
    import urllib.request
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import polars as pl

    root = Path(__file__).resolve().parent
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    def is_wasm_runtime():
        app_object = getattr(mo, "app", None)
        is_wasm = getattr(app_object, "is_wasm", None)
        return bool(is_wasm()) if callable(is_wasm) else False

    running_in_wasm = is_wasm_runtime()
    try:
        import analysis
    except ModuleNotFoundError:
        analysis = None
        running_in_wasm = True

    def read_pages_csv(filename):
        attempted = []
        for url in (f"data/pages/{filename}", f"./data/pages/{filename}", f"../data/pages/{filename}"):
            attempted.append(url)
            try:
                with urllib.request.urlopen(url) as response:
                    payload = response.read()
            except Exception:
                continue
            if payload.lstrip().startswith((b"<!DOCTYPE", b"<html")):
                continue
            return pl.read_csv(io.BytesIO(payload), try_parse_dates=True)
        raise FileNotFoundError("Pages用CSVを取得できませんでした: " + ", ".join(attempted))

    if running_in_wasm or analysis is None:
        def load_data():
            return (
                read_pages_csv("annual_metrics.csv"),
                read_pages_csv("daily_cumulative.csv"),
                read_pages_csv("monthly_metrics.csv"),
                read_pages_csv("streaks.csv"),
            )

        def period_slice(frame, start_year, end_year):
            lower, upper = sorted((start_year, end_year))
            return frame.filter(pl.col("year").is_between(lower, upper))

        def format_number(value, digits=1, suffix=""):
            return "-" if value is None else f"{float(value):,.{digits}f}{suffix}"

        def difference(left, right, digits=1):
            return "-" if left is None or right is None else f"{float(right) - float(left):+,.{digits}f}"
    else:
        analysis = importlib.reload(analysis)

        def load_data():
            return tuple(analysis.load_table(name) for name in ("annual", "daily", "monthly", "streaks"))

        period_slice = analysis.period_slice
        format_number = analysis.format_number
        difference = analysis.difference

    COLORS = {
        "rain": "#2878a5",
        "rain_dark": "#16506f",
        "days": "#48a4a1",
        "cumulative": "#e07a3f",
        "band": "#c8d8df",
        "reference": "#8b6bb1",
        "dry": "#d3a62c",
    }

    def stat_cards(cards):
        body = "".join(
            f"""
            <section class="rain-card" style="--accent:{card['color']}">
              <div class="rain-label">{card['label']}</div>
              <div class="rain-value">{card['value']}</div>
              <div class="rain-caption">{card['caption']}</div>
            </section>
            """
            for card in cards
        )
        return mo.Html(
            f"""
            <style>
              .rain-grid {{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));}}
              .rain-card {{background:#fff;border:1px solid #dbe6e9;border-left:5px solid var(--accent);border-radius:9px;
                box-shadow:0 8px 22px rgba(18,47,61,.08);padding:14px 16px;min-height:102px;color:#18313d;}}
              .rain-label {{font-size:13px;font-weight:700;color:#64777f;}}
              .rain-value {{font-size:27px;font-weight:800;line-height:1.25;margin-top:7px;}}
              .rain-caption {{font-size:12px;color:#72848b;margin-top:7px;}}
              @media(max-width:640px){{.rain-grid{{grid-template-columns:1fr;}}.rain-value{{font-size:24px;}}}}
            </style><div class="rain-grid">{body}</div>
            """
        )

    return COLORS, alt, difference, format_number, load_data, mo, period_slice, pl, stat_cards


@app.cell
def _(load_data, pl):
    annual, daily, monthly, streaks = load_data()
    annual = annual.with_columns(
        pl.col("year").cast(pl.Int64),
        pl.col("period_start_date").cast(pl.Date),
        pl.col("period_end_date").cast(pl.Date),
    )
    daily = daily.with_columns(pl.col("year").cast(pl.Int64), pl.col("observed_date").cast(pl.Date))
    monthly = monthly.with_columns(
        pl.col("year").cast(pl.Int64),
        pl.col("month").cast(pl.Int64),
        pl.col("month_start").cast(pl.Date),
    )
    streaks = streaks.with_columns(
        pl.col("streak_start_date").cast(pl.Date),
        pl.col("streak_end_date").cast(pl.Date),
    )
    complete_annual = annual.filter(pl.col("is_complete_calendar_year"))
    incomplete_annual = annual.filter(~pl.col("is_complete_calendar_year"))
    return annual, complete_annual, daily, incomplete_annual, monthly, streaks


@app.cell
def _(annual, complete_annual, mo):
    start_year = int(annual["year"].min())
    end_year = int(annual["year"].max())
    complete_end_year = int(complete_annual["year"].max())
    year_options = [str(year) for year in annual["year"].to_list()]
    complete_year_options = [str(year) for year in complete_annual["year"].to_list()]
    target_start_year = mo.ui.dropdown(year_options, value=str(start_year), label="表示開始年")
    target_end_year = mo.ui.dropdown(year_options, value=str(end_year), label="表示終了年")
    target_controls = mo.hstack([target_start_year, target_end_year], gap=2, justify="start")
    return complete_end_year, complete_year_options, end_year, start_year, target_controls, target_end_year, target_start_year, year_options


@app.cell
def _(annual, complete_annual, target_end_year, target_start_year, pl):
    target_start, target_end = sorted((int(target_start_year.value), int(target_end_year.value)))
    shown_annual = annual.filter(pl.col("year").is_between(target_start, target_end))
    shown_complete = complete_annual.filter(pl.col("year").is_between(target_start, target_end))
    return shown_annual, shown_complete, target_end, target_start


@app.cell
def _(COLORS, alt, mo, pl, shown_annual, shown_complete, target_controls, target_end, target_start):
    annual_long = shown_annual.unpivot(
        index=["year", "is_complete_calendar_year"],
        on=["annual_precipitation_mm", "precipitation_days"],
        variable_name="metric",
        value_name="value",
    ).with_columns(
        pl.col("metric").replace({"annual_precipitation_mm": "年間降水量", "precipitation_days": "降水日数"})
    )
    year_pick = alt.selection_point(name="selected_year", fields=["year"], empty=True, clear="dblclick")
    complete_lines = alt.Chart().transform_filter(
        alt.FieldEqualPredicate(field="is_complete_calendar_year", equal=True)
    ).mark_line(point=True, strokeWidth=2.3).encode(
        x=alt.X("year:Q", title="年", axis=alt.Axis(format="d"), scale=alt.Scale(domain=[target_start - 1, target_end + 1])),
        y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False)),
        color=alt.Color("metric:N", title="指標", scale=alt.Scale(domain=["年間降水量", "降水日数"], range=[COLORS["rain"], COLORS["days"]])),
        tooltip=[alt.Tooltip("year:Q", title="年", format="d"), alt.Tooltip("metric:N", title="指標"), alt.Tooltip("value:Q", title="値", format=",.1f")],
    )
    reference_points = alt.Chart().transform_filter(
        alt.FieldEqualPredicate(field="is_complete_calendar_year", equal=False)
    ).mark_point(shape="triangle-up", size=90, filled=True, color=COLORS["reference"]).encode(
        x=alt.X("year:Q", axis=alt.Axis(format="d")), y=alt.Y("value:Q"),
        tooltip=[alt.Tooltip("year:Q", title="年", format="d"), alt.Tooltip("metric:N", title="指標"), alt.Tooltip("value:Q", title="参考値", format=",.1f")],
    )
    annual_chart = alt.layer(complete_lines, reference_points).properties(
        width="container", height=155,
    ).facet(
        data=annual_long,
        row=alt.Row("metric:N", title=None, header=alt.Header(labelFontSize=13)),
    ).resolve_scale(y="independent").add_params(year_pick).properties(title="年間降水量・降水日数の長期推移", bounds="flush")
    annual_chart_ui = mo.ui.altair_chart(annual_chart)
    incomplete_years = "、".join(str(year) for year in shown_annual.filter(~pl.col("is_complete_calendar_year"))["year"].to_list()) or "なし"
    overview = mo.vstack([
        mo.md("# 東京の雨を100年で見る"), target_controls,
        mo.md(
            f"""東京（北の丸公園）の `{target_start}`〜`{target_end}` 年を表示しています。
            線・平均・ランキングには観測が揃った `{shown_complete.height}` 年だけを使用します。
            ▲は不完全年・欠測年の参考値です（該当: {incomplete_years}）。グラフの点をクリックすると年詳細が切り替わります。

            **降水日の定義:** 気象庁の「現象なし情報」が `0` の日です。したがって **0.0mmでも微量降水現象があれば降水日**、
            「現象なし情報」が `1` の日は無降水として区別します。"""
        ), annual_chart_ui,
    ], gap=2)
    overview
    return (annual_chart_ui,)


@app.cell
def _(annual_chart_ui, shown_annual):
    selected_year = int(shown_annual["year"].max())
    selected = annual_chart_ui.value
    if selected is not None and len(selected) > 0:
        if hasattr(selected, "row"):
            selected_year = int(selected.row(0, named=True)["year"])
        elif hasattr(selected, "to_dicts"):
            selected_year = int(selected.to_dicts()[0]["year"])
        elif isinstance(selected, dict):
            selected_year = int(selected["year"][0] if isinstance(selected["year"], list) else selected["year"])
        else:
            selected_year = int(selected[0]["year"])
    return (selected_year,)


@app.cell
def _(COLORS, alt, complete_annual, daily, format_number, mo, pl, selected_year, stat_cards):
    selected_row = complete_annual.filter(pl.col("year") == selected_year)
    is_reference = selected_row.is_empty()
    selected_row = (selected_row if not is_reference else daily.filter(
        (pl.col("year") == selected_year) & (pl.col("quality_code") == 8)
    ).select(
        pl.lit(selected_year).alias("year"),
        pl.col("precipitation_mm").sum().alias("annual_precipitation_mm"),
        pl.col("is_precipitation_day").sum().alias("precipitation_days"),
        pl.col("is_measurable_precipitation_day").sum().alias("measurable_precipitation_days"),
        pl.col("precipitation_mm").max().alias("max_daily_precipitation_mm"),
    )).row(0, named=True)
    selected_daily = daily.filter(pl.col("year") == selected_year).with_columns(
        pl.date(pl.lit(2004), pl.col("month"), pl.col("day")).alias("plot_date")
    )
    baseline = daily.join(complete_annual.select("year"), on="year", how="inner").filter(
        ~((pl.col("month") == 2) & (pl.col("day") == 29))
    ).group_by(["month", "day"]).agg(
        pl.col("cumulative_precipitation_mm").quantile(.25).alias("p25_cumulative_mm"),
        pl.col("cumulative_precipitation_mm").quantile(.75).alias("p75_cumulative_mm"),
        pl.col("cumulative_precipitation_mm").median().alias("median_cumulative_mm"),
    ).with_columns(pl.date(pl.lit(2004), pl.col("month"), pl.col("day")).alias("plot_date")).sort("plot_date")
    bars = alt.Chart(selected_daily).mark_bar(color=COLORS["rain"], opacity=.62).encode(
        x=alt.X("plot_date:T", title="月日", axis=alt.Axis(format="%m/%d")),
        y=alt.Y("precipitation_mm:Q", title="日降水量 (mm)"),
        tooltip=[alt.Tooltip("observed_date:T", title="日付", format="%Y/%m/%d"), alt.Tooltip("precipitation_mm:Q", title="日降水量 (mm)", format=".1f"), alt.Tooltip("has_precipitation_phenomenon:N", title="降水現象あり")],
    )
    band = alt.Chart(baseline).mark_area(color=COLORS["band"], opacity=.42).encode(
        x=alt.X("plot_date:T"), y=alt.Y("p25_cumulative_mm:Q", title="年内累計 (mm)"), y2="p75_cumulative_mm:Q"
    )
    median = alt.Chart(baseline).mark_line(color="#78909a", strokeDash=[5, 4]).encode(x="plot_date:T", y="median_cumulative_mm:Q")
    cumulative = alt.Chart(selected_daily).mark_line(color=COLORS["cumulative"], strokeWidth=3).encode(
        x=alt.X("plot_date:T"), y=alt.Y("cumulative_precipitation_mm:Q", title="年内累計 (mm)"),
        tooltip=[alt.Tooltip("observed_date:T", title="日付", format="%Y/%m/%d"), alt.Tooltip("cumulative_precipitation_mm:Q", title="年内累計 (mm)", format=",.1f")],
    )
    daily_chart = alt.layer(bars, band, median, cumulative).resolve_scale(y="independent").properties(
        title=f"{selected_year}年の日降水量と年内累計", width="container", height=330
    )
    trace_days = int(selected_row["precipitation_days"] - selected_row["measurable_precipitation_days"])
    cards = stat_cards([
        {"label": "年内累計降水量" if is_reference else "年間降水量", "value": format_number(selected_row["annual_precipitation_mm"], 1, " mm"), "caption": "途中時点の参考値" if is_reference else "完全な暦年", "color": COLORS["rain"]},
        {"label": "降水日数", "value": format_number(selected_row["precipitation_days"], 0, "日"), "caption": f"うち0.0mmの微量降水 {trace_days}日", "color": COLORS["days"]},
        {"label": "最大日降水量", "value": format_number(selected_row["max_daily_precipitation_mm"], 1, " mm"), "caption": "品質コード8の観測", "color": COLORS["cumulative"]},
    ])
    reference_note = "**参考値:** この年は年途中または欠測を含むため、年間ランキング・平均・期間比較から除外しています。" if is_reference else "この年は完全な暦年として年間統計に含まれます。"
    detail_panel = mo.vstack([
        mo.md(f"## {selected_year}年詳細\n{reference_note}\n\n灰色帯は **完全年（1926〜2025年、欠測年を除く）の年内累積降水量** の25〜75%点、破線は中央値です。日降水量の分布ではありません。"),
        cards, mo.ui.altair_chart(daily_chart),
    ], gap=2)
    detail_panel
    return


@app.cell
def _(mo):
    ranking_metric = mo.ui.radio(
        options={"年間降水量": "annual_precipitation_mm", "降水日数": "precipitation_days", "年内最長連続降水": "longest_precipitation_streak_days"},
        value="年間降水量", inline=True, label="ランキング指標",
    )
    ranking_top_n = mo.ui.dropdown(["3", "5", "10"], value="5", label="上位件数")
    ranking_controls = mo.hstack([ranking_metric, ranking_top_n], gap=2, justify="start")
    return ranking_controls, ranking_metric, ranking_top_n


@app.cell
def _(COLORS, alt, complete_annual, format_number, mo, pl, ranking_controls, ranking_metric, ranking_top_n, streaks):
    metric = ranking_metric.value
    metric_label = {"annual_precipitation_mm": "年間降水量", "precipitation_days": "降水日数", "longest_precipitation_streak_days": "年内最長連続降水"}[metric]
    unit = " mm" if metric == "annual_precipitation_mm" else "日"
    ranked = complete_annual.sort(metric, descending=True).head(int(ranking_top_n.value)).select("year", metric)
    rank_rows = "".join(
        f"<div class='rank-row'><b>{_index + 1}</b><span>{int(_row['year'])}年</span><strong>{format_number(_row[metric], 1 if metric == 'annual_precipitation_mm' else 0, unit)}</strong></div>"
        for _index, _row in enumerate(ranked.iter_rows(named=True))
    )
    rank_html = mo.Html(
        f"""<style>.rank-board{{max-width:620px;background:#fff;border:1px solid #dbe6e9;border-top:5px solid {COLORS['rain']};border-radius:9px;padding:10px 15px}}
        .rank-row{{display:grid;grid-template-columns:32px 1fr auto;align-items:center;min-height:38px;border-top:1px solid #edf2f3}}.rank-row:first-child{{border:0}}
        .rank-row b{{color:{COLORS['rain_dark']}}}.rank-row strong{{color:{COLORS['rain_dark']};font-size:16px}}</style><div class='rank-board'>{rank_rows}</div>"""
    )
    ranked_years = ranked["year"].to_list()
    trend = complete_annual.select("year", metric).with_columns(pl.col("year").is_in(ranked_years).alias("top"))
    trend_line = alt.Chart(trend).mark_line(color=COLORS["rain"]).encode(
        x=alt.X("year:Q", title="年", axis=alt.Axis(format="d")), y=alt.Y(f"{metric}:Q", title=f"{metric_label} ({unit.strip()})", scale=alt.Scale(zero=False))
    )
    trend_points = alt.Chart(trend).mark_point(filled=True, color=COLORS["rain"]).encode(
        x=alt.X("year:Q", axis=alt.Axis(format="d")), y=f"{metric}:Q",
        opacity=alt.condition(alt.datum.top, alt.value(1), alt.value(.18)), size=alt.condition(alt.datum.top, alt.value(105), alt.value(20)),
        tooltip=[alt.Tooltip("year:Q", title="年", format="d"), alt.Tooltip(f"{metric}:Q", title=metric_label, format=",.1f")],
    )
    all_time = streaks.filter(pl.col("streak_type") == "precipitation").sort(
        "streak_length", descending=True
    ).head(1).row(0, named=True)
    ranking_panel = mo.vstack([
        mo.md("## 年間ランキング"), ranking_controls,
        mo.md("ランキングは完全な暦年のみ。年内最長連続降水は **1月1日〜12月31日にクリップした値** です。"),
        rank_html, mo.ui.altair_chart((trend_line + trend_points).properties(title=f"{metric_label}の推移", width="container", height=290)),
        mo.md(f"**全期間の年跨ぎを含む最長連続降水:** `{all_time['streak_length']}日`（{all_time['streak_start_date']}〜{all_time['streak_end_date']}）。これは年内ランキングとは別指標です。"),
    ], gap=2)
    ranking_panel
    return


@app.cell
def _(complete_end_year, complete_year_options, mo, start_year):
    left_start = mo.ui.dropdown(complete_year_options, value="1926" if start_year <= 1926 else complete_year_options[0], label="比較A 開始")
    left_end = mo.ui.dropdown(complete_year_options, value="1955" if "1955" in complete_year_options else complete_year_options[29], label="比較A 終了")
    right_start = mo.ui.dropdown(complete_year_options, value="1996" if "1996" in complete_year_options else complete_year_options[-30], label="比較B 開始")
    right_end = mo.ui.dropdown(complete_year_options, value=str(complete_end_year), label="比較B 終了")
    compare_controls = mo.hstack([left_start, left_end, right_start, right_end], gap=2, justify="start")
    return compare_controls, left_end, left_start, right_end, right_start


@app.cell
def _(COLORS, complete_annual, difference, format_number, left_end, left_start, mo, period_slice, pl, right_end, right_start, compare_controls, stat_cards):
    left = period_slice(complete_annual, int(left_start.value), int(left_end.value))
    right = period_slice(complete_annual, int(right_start.value), int(right_end.value))
    left_label = f"{left['year'].min()}–{left['year'].max()}（{left.height}年）"
    right_label = f"{right['year'].min()}–{right['year'].max()}（{right.height}年）"
    comparison_rows = []
    for _label, _metric, _digits, _unit in (
        ("年間降水量", "annual_precipitation_mm", 1, "mm"),
        ("降水日数", "precipitation_days", 1, "日"),
        ("0mm超の降水日数", "measurable_precipitation_days", 1, "日"),
        ("年内最長連続降水", "longest_precipitation_streak_days", 1, "日"),
    ):
        _left_mean = left[_metric].mean()
        _right_mean = right[_metric].mean()
        comparison_rows.append((_label, format_number(_left_mean, _digits, _unit), format_number(_right_mean, _digits, _unit), difference(_left_mean, _right_mean, _digits) + _unit))
    comparison = pl.DataFrame(comparison_rows, schema=["指標", left_label, right_label, "差（B−A）"], orient="row")
    impact = stat_cards([
        {"label": "年間降水量の差", "value": difference(left["annual_precipitation_mm"].mean(), right["annual_precipitation_mm"].mean(), 1) + " mm", "caption": f"{left_label} → {right_label}", "color": COLORS["rain"]},
        {"label": "降水日数の差", "value": difference(left["precipitation_days"].mean(), right["precipitation_days"].mean(), 1) + "日", "caption": "0.0mmの微量降水も含む", "color": COLORS["days"]},
        {"label": "連続降水の差", "value": difference(left["longest_precipitation_streak_days"].mean(), right["longest_precipitation_streak_days"].mean(), 1) + "日", "caption": "年内最長値の平均", "color": COLORS["reference"]},
    ])
    compare_panel = mo.vstack([
        mo.md("## 期間比較"),
        mo.md("開始・終了の順序は自動で補正し、各期間内の **完全年だけ** を比較します。欠測年と2026年は入りません。"),
        compare_controls, impact, mo.ui.table(comparison, pagination=False),
    ], gap=2)
    compare_panel
    return


@app.cell
def _(mo):
    month_selector = mo.ui.dropdown([f"{month}月" for month in range(1, 13)], value="9月", label="比較する月")
    return (month_selector,)


@app.cell
def _(COLORS, alt, mo, month_selector, monthly, pl, target_end, target_start):
    selected_month = int(month_selector.value.removesuffix("月"))
    complete_monthly = monthly.with_columns(pl.col("month_start").dt.month_end().dt.day().alias("days_in_month")).filter(
        pl.col("complete_observation_days") == pl.col("days_in_month")
    )
    month_view = complete_monthly.filter(
        (pl.col("month") == selected_month) & pl.col("year").is_between(target_start, target_end)
    )
    month_long = month_view.unpivot(
        index="year", on=["precipitation_mm", "precipitation_days", "measurable_precipitation_days"], variable_name="metric", value_name="value"
    ).with_columns(pl.col("metric").replace({"precipitation_mm": "月降水量", "precipitation_days": "降水日数", "measurable_precipitation_days": "0mm超の日数"}))
    month_chart = alt.Chart(month_long).mark_line(point=True).encode(
        x=alt.X("year:Q", title="年", axis=alt.Axis(format="d")), y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False)),
        color=alt.Color("metric:N", title="指標", scale=alt.Scale(domain=["月降水量", "降水日数", "0mm超の日数"], range=[COLORS["rain"], COLORS["days"], COLORS["cumulative"]])),
        tooltip=[alt.Tooltip("year:Q", title="年", format="d"), alt.Tooltip("metric:N", title="指標"), alt.Tooltip("value:Q", title="値", format=",.1f")],
    ).properties(width="container", height=145).facet(row=alt.Row("metric:N", title=None)).resolve_scale(y="independent").properties(title=f"{selected_month}月の比較（完全な月のみ）", bounds="flush")
    month_panel = mo.vstack([
        mo.md("## 月別比較"),
        mo.md("冒頭の表示期間について、選択月の月降水量・降水日数を比較します。月の全日が品質コード8で揃った月だけを表示します。"),
        month_selector, mo.ui.altair_chart(month_chart),
    ], gap=2)
    month_panel
    return


if __name__ == "__main__":
    app.run()

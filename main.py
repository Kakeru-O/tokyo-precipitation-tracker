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
        for url in (
            f"data/pages/{filename}",
            f"./data/pages/{filename}",
            f"../data/pages/{filename}",
        ):
            attempted.append(url)
            try:
                with urllib.request.urlopen(url) as response:
                    payload = response.read()
            except Exception:
                continue
            if payload.lstrip().startswith((b"<!DOCTYPE", b"<html")):
                continue
            return pl.read_csv(io.BytesIO(payload), try_parse_dates=True)
        raise FileNotFoundError(
            "Pages用CSVを取得できませんでした: " + ", ".join(attempted)
        )

    if running_in_wasm or analysis is None:

        def load_data():
            return (
                read_pages_csv("annual_metrics.csv"),
                read_pages_csv("daily_cumulative.csv"),
                read_pages_csv("period_metrics.csv"),
                read_pages_csv("streaks.csv"),
            )

        def format_number(value, digits=1, suffix=""):
            return "-" if value is None else f"{float(value):,.{digits}f}{suffix}"

    else:
        analysis = importlib.reload(analysis)

        def load_data():
            return tuple(
                analysis.load_table(name)
                for name in ("annual", "daily", "periods", "streaks")
            )

        format_number = analysis.format_number

    COLORS = {
        "rain": "#2474a6",
        "rain_dark": "#164f70",
        "days": "#2d918d",
        "cumulative": "#df7541",
        "band": "#c8d8df",
        "reference": "#8b6bb1",
        "intensity": "#c78b22",
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
              .rain-grid {{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));}}
              .rain-card {{background:#fff;border:1px solid #dbe6e9;border-left:5px solid var(--accent);
                border-radius:9px;box-shadow:0 8px 22px rgba(18,47,61,.08);padding:14px 16px;
                min-height:105px;color:#18313d;}}
              .rain-label {{font-size:13px;font-weight:700;color:#64777f;}}
              .rain-value {{font-size:26px;font-weight:800;line-height:1.25;margin-top:7px;}}
              .rain-caption {{font-size:12px;color:#72848b;margin-top:7px;line-height:1.45;}}
              @media(max-width:640px){{.rain-grid{{grid-template-columns:1fr;}}.rain-value{{font-size:23px;}}}}
            </style><div class="rain-grid">{body}</div>
            """
        )

    def rank_caption(frame, metric, year, digits, unit):
        row = frame.filter(pl.col("year") == year)
        if row.is_empty():
            return "参考値・ランキング対象外"
        value = row[metric].item()
        valid = frame.drop_nulls([metric]).with_columns(
            pl.col(metric).rank(method="min", descending=True).alias("rank")
        )
        rank = int(valid.filter(pl.col("year") == year)["rank"].item())
        delta = float(value) - float(valid[metric].mean())
        return f"完全年{valid.height}年中 {rank}位・長期平均比 {delta:+,.{digits}f}{unit}"

    return (
        COLORS,
        alt,
        format_number,
        load_data,
        mo,
        pl,
        rank_caption,
        stat_cards,
    )


@app.cell
def _(load_data, pl):
    annual, daily, periods, streaks = load_data()
    annual = annual.with_columns(
        pl.col("year").cast(pl.Int64),
        pl.col("period_start_date").cast(pl.Date),
        pl.col("period_end_date").cast(pl.Date),
    )
    daily = daily.with_columns(
        pl.col("year").cast(pl.Int64),
        pl.col("observed_date").cast(pl.Date),
    )
    periods = periods.with_columns(
        pl.col("year").cast(pl.Int64),
        pl.col("expected_start_date").cast(pl.Date),
        pl.col("expected_end_date").cast(pl.Date),
        pl.col("observed_start_date").cast(pl.Date),
        pl.col("observed_end_date").cast(pl.Date),
    )
    streaks = streaks.with_columns(
        pl.col("streak_start_date").cast(pl.Date),
        pl.col("streak_end_date").cast(pl.Date),
    )
    complete_annual = annual.filter(pl.col("is_complete_calendar_year"))
    return annual, complete_annual, daily, periods, streaks


@app.cell
def _(annual, mo):
    start_year = int(annual["year"].min())
    end_year = int(annual["year"].max())
    year_options = [str(year) for year in annual["year"].to_list()]
    target_start_year = mo.ui.dropdown(
        year_options, value=str(start_year), label="表示開始年"
    )
    target_end_year = mo.ui.dropdown(
        year_options, value=str(end_year), label="表示終了年"
    )
    target_controls = mo.hstack(
        [target_start_year, target_end_year], gap=2, justify="start", wrap=True
    )
    return target_controls, target_end_year, target_start_year


@app.cell
def _(annual, complete_annual, pl, target_end_year, target_start_year):
    target_start, target_end = sorted(
        (int(target_start_year.value), int(target_end_year.value))
    )
    shown_annual = annual.filter(pl.col("year").is_between(target_start, target_end))
    shown_complete = complete_annual.filter(
        pl.col("year").is_between(target_start, target_end)
    )
    return shown_annual, shown_complete, target_end, target_start


@app.cell
def _(
    COLORS,
    alt,
    mo,
    pl,
    shown_annual,
    shown_complete,
    target_controls,
    target_end,
    target_start,
):
    year_selection = alt.selection_point(
        name="selected_year_point",
        fields=["year"],
        empty=True,
        clear="dblclick",
    )
    chart_data = shown_annual.with_columns(
        pl.when(pl.col("is_complete_calendar_year"))
        .then(pl.lit("暦年の観測完了"))
        .when(
            (pl.col("period_end_date").dt.month() < 12)
            | (pl.col("period_end_date").dt.day() < 31)
        )
        .then(
            pl.format(
                "{}月{}日時点の参考値",
                pl.col("period_end_date").dt.month(),
                pl.col("period_end_date").dt.day(),
            )
        )
        .otherwise(pl.lit("欠測を含む参考値"))
        .alias("status_label")
    )
    x_encoding = alt.X(
        "year:Q",
        title="年（クリックで詳細を表示）",
        axis=alt.Axis(format="d", tickCount=8, labelAngle=0, labelOverlap="greedy"),
        scale=alt.Scale(domain=[target_start - 1, target_end + 1]),
    )
    rainfall_bars = (
        alt.Chart(chart_data)
        .mark_bar(color=COLORS["rain"], size=6)
        .encode(
            x=x_encoding,
            y=alt.Y(
                "annual_precipitation_mm:Q",
                title="降水量（mm）",
                axis=alt.Axis(titleColor=COLORS["rain_dark"]),
                scale=alt.Scale(zero=True),
            ),
            opacity=alt.condition(year_selection, alt.value(0.82), alt.value(0.25)),
            tooltip=[
                alt.Tooltip("year:Q", title="年", format="d"),
                alt.Tooltip("annual_precipitation_mm:Q", title="降水量", format=",.1f"),
                alt.Tooltip("precipitation_days:Q", title="降水日数", format=",.0f"),
                alt.Tooltip("status_label:N", title="集計状態"),
            ],
        )
    )
    reference_points = (
        alt.Chart(chart_data)
        .transform_filter(
            alt.FieldEqualPredicate(field="is_complete_calendar_year", equal=False)
        )
        .mark_point(
            shape="triangle-up", size=95, filled=True, color=COLORS["reference"]
        )
        .encode(
            x=x_encoding,
            y=alt.Y("annual_precipitation_mm:Q", title="降水量（mm）"),
            tooltip=[
                alt.Tooltip("year:Q", title="年", format="d"),
                alt.Tooltip("annual_precipitation_mm:Q", title="参考値", format=",.1f"),
                alt.Tooltip("status_label:N", title="集計状態"),
            ],
        )
    )
    days_line = (
        alt.Chart(chart_data)
        .mark_line(point=False, strokeWidth=2.2, color=COLORS["days"])
        .encode(
            x=x_encoding,
            y=alt.Y(
                "precipitation_days:Q",
                title="降水日数（日）",
                axis=alt.Axis(orient="right", titleColor=COLORS["days"], grid=False),
                scale=alt.Scale(zero=True),
            ),
        )
    )
    days_points = (
        alt.Chart(chart_data)
        .mark_point(filled=True, size=40, color=COLORS["days"])
        .encode(
            x=x_encoding,
            y=alt.Y("precipitation_days:Q", title="降水日数（日）"),
            opacity=alt.condition(year_selection, alt.value(1), alt.value(0.28)),
            tooltip=[
                alt.Tooltip("year:Q", title="年", format="d"),
                alt.Tooltip("precipitation_days:Q", title="降水日数", format=",.0f"),
                alt.Tooltip("annual_precipitation_mm:Q", title="降水量", format=",.1f"),
                alt.Tooltip("status_label:N", title="集計状態"),
            ],
        )
    )
    annual_chart = (
        alt.layer(rainfall_bars, reference_points, days_line, days_points)
        .resolve_scale(y="independent")
        .add_params(year_selection)
        .properties(
            title={
                "text": "東京の降水量と雨の日の長期推移",
                "subtitle": [
                    "青い棒＝降水量（左軸） / 緑の線＝降水日数（右軸）",
                    "▲は年途中または欠測を含む参考値",
                ],
            },
            width="container",
            height=340,
        )
    )
    annual_chart_ui = mo.ui.altair_chart(annual_chart)
    latest = shown_annual.sort("year").tail(1).row(0, named=True)
    latest_note = ""
    if not latest["is_complete_calendar_year"]:
        _latest_end_date = latest["period_end_date"]
        latest_note = (
            f"> **{latest['year']}年は{_latest_end_date.month}月{_latest_end_date.day}日までの観測値です。** "
            "年間の確定値ではありません。"
        )
    overview = mo.vstack(
        [
            mo.md("# 東京の降水量と雨の日の変化"),
            mo.md(
                "東京（北の丸公園）の雨を、長期推移と年ごとの降り方から振り返ります。"
                "グラフ上の年をクリックすると、その年の詳細に切り替わります。"
            ),
            target_controls,
            mo.md(
                f"`{target_start}`〜`{target_end}`年を表示（比較に使える完全年は"
                f"`{shown_complete.height}`年）。\n\n{latest_note}"
            ),
            annual_chart_ui,
        ],
        gap=2,
    )
    overview
    return (annual_chart_ui,)


@app.cell
def _(annual_chart_ui, shown_annual):
    selected_year = (
        int(shown_annual["year"].max()) if not shown_annual.is_empty() else None
    )
    clicked = annual_chart_ui.value
    if clicked is not None and len(clicked) > 0:
        if hasattr(clicked, "row"):
            selected_year = int(clicked.row(0, named=True)["year"])
        elif isinstance(clicked, dict):
            value = clicked["year"]
            selected_year = int(value[0] if isinstance(value, list) else value)
        elif hasattr(clicked, "to_dicts"):
            selected_year = int(clicked.to_dicts()[0]["year"])
        elif hasattr(clicked, "to_dict"):
            selected_year = int(clicked.to_dict("records")[0]["year"])
        else:
            selected_year = int(clicked[0]["year"])
    return (selected_year,)


@app.cell
def _(
    COLORS,
    alt,
    annual,
    complete_annual,
    daily,
    format_number,
    mo,
    pl,
    rank_caption,
    selected_year,
    stat_cards,
):
    selected_frame = annual.filter(pl.col("year") == selected_year)
    selected_row = selected_frame.row(0, named=True)
    is_reference = not selected_row["is_complete_calendar_year"]
    selected_daily = daily.filter(pl.col("year") == selected_year).with_columns(
        pl.date(pl.lit(2004), pl.col("month"), pl.col("day")).alias("plot_date")
    )
    baseline = (
        daily.join(complete_annual.select("year"), on="year", how="inner")
        .filter(~((pl.col("month") == 2) & (pl.col("day") == 29)))
        .group_by(["month", "day"])
        .agg(
            pl.col("cumulative_precipitation_mm")
            .quantile(0.25)
            .alias("p25_cumulative_mm"),
            pl.col("cumulative_precipitation_mm")
            .quantile(0.75)
            .alias("p75_cumulative_mm"),
            pl.col("cumulative_precipitation_mm")
            .median()
            .alias("median_cumulative_mm"),
        )
        .with_columns(
            pl.date(pl.lit(2004), pl.col("month"), pl.col("day")).alias("plot_date")
        )
        .sort("plot_date")
    )
    month_axis = alt.Axis(
        format="%m月", tickCount=6, labelAngle=0, labelOverlap="greedy"
    )
    daily_rainfall_chart = (
        alt.Chart(selected_daily)
        .mark_bar(color=COLORS["rain"], opacity=0.68)
        .encode(
            x=alt.X("plot_date:T", title="月", axis=month_axis),
            y=alt.Y("precipitation_mm:Q", title="日降水量（mm）", scale=alt.Scale(zero=True)),
            tooltip=[
                alt.Tooltip("observed_date:T", title="日付", format="%Y/%m/%d"),
                alt.Tooltip("precipitation_mm:Q", title="日降水量", format=".1f"),
            ],
        )
        .properties(title=f"{selected_year}年の日降水量", width="container", height=220)
    )
    band = (
        alt.Chart(baseline)
        .mark_area(color=COLORS["band"], opacity=0.45)
        .encode(
            x=alt.X("plot_date:T", title="月", axis=month_axis),
            y=alt.Y(
                "p25_cumulative_mm:Q",
                title="年内累計降水量（mm）",
                scale=alt.Scale(zero=True),
            ),
            y2="p75_cumulative_mm:Q",
            tooltip=[
                alt.Tooltip("plot_date:T", title="月日", format="%m/%d"),
                alt.Tooltip("p25_cumulative_mm:Q", title="25%点", format=",.1f"),
                alt.Tooltip("p75_cumulative_mm:Q", title="75%点", format=",.1f"),
            ],
        )
    )
    median = (
        alt.Chart(baseline)
        .mark_line(color="#78909a", strokeDash=[5, 4])
        .encode(x="plot_date:T", y="median_cumulative_mm:Q")
    )
    cumulative = (
        alt.Chart(selected_daily)
        .mark_line(color=COLORS["cumulative"], strokeWidth=3)
        .encode(
            x=alt.X("plot_date:T", title="月", axis=month_axis),
            y=alt.Y(
                "cumulative_precipitation_mm:Q",
                title="年内累計降水量（mm）",
                scale=alt.Scale(zero=True),
            ),
            tooltip=[
                alt.Tooltip("observed_date:T", title="日付", format="%Y/%m/%d"),
                alt.Tooltip(
                    "cumulative_precipitation_mm:Q", title="年内累計", format=",.1f"
                ),
                alt.Tooltip(
                    "cumulative_precipitation_days:Q", title="累計降水日数", format=",.0f"
                ),
            ],
        )
    )
    cumulative_chart = (band + median + cumulative).properties(
        title="年内累計降水量（灰色帯は完全年の25〜75%点、破線は中央値）",
        width="container",
        height=260,
    )
    _detail_end_date = selected_row["period_end_date"]
    if not is_reference:
        detail_title = f"## {selected_year}年の雨"
    elif _detail_end_date.month == 12 and _detail_end_date.day == 31:
        detail_title = f"## {selected_year}年の雨（欠測あり・参考値）"
    else:
        detail_title = (
            f"## {selected_year}年の雨"
            f"（{_detail_end_date.month}月{_detail_end_date.day}日時点）"
        )
    reference_note = (
        "この年は完全な暦年として順位と長期平均との差を表示します。"
        if not is_reference
        else "**参考値:** 年途中または欠測を含むため、順位・長期平均の計算には含めません。"
    )
    cards = stat_cards(
        [
            {
                "label": "年内累計降水量" if is_reference else "年間降水量",
                "value": format_number(selected_row["annual_precipitation_mm"], 1, " mm"),
                "caption": rank_caption(
                    complete_annual, "annual_precipitation_mm", selected_year, 1, " mm"
                ),
                "color": COLORS["rain"],
            },
            {
                "label": "降水日数",
                "value": format_number(selected_row["precipitation_days"], 0, "日"),
                "caption": rank_caption(
                    complete_annual, "precipitation_days", selected_year, 1, "日"
                ),
                "color": COLORS["days"],
            },
            {
                "label": "降水1日あたりの平均降水量",
                "value": format_number(
                    selected_row["mean_precipitation_per_precipitation_day_mm"], 1, " mm"
                ),
                "caption": rank_caption(
                    complete_annual,
                    "mean_precipitation_per_precipitation_day_mm",
                    selected_year,
                    1,
                    " mm",
                ),
                "color": COLORS["intensity"],
            },
            {
                "label": "最大日降水量",
                "value": format_number(
                    selected_row["max_daily_precipitation_mm"], 1, " mm"
                ),
                "caption": rank_caption(
                    complete_annual, "max_daily_precipitation_mm", selected_year, 1, " mm"
                ),
                "color": COLORS["cumulative"],
            },
        ]
    )
    detail_panel = mo.vstack(
        [
            mo.md(f"{detail_title}\n\n{reference_note}"),
            cards,
            daily_rainfall_chart,
            cumulative_chart,
        ],
        gap=2,
    )
    detail_panel
    return


@app.cell
def _(mo):
    ranking_metric = mo.ui.dropdown(
        options={
            "年間降水量": "annual_precipitation_mm",
            "降水日数": "precipitation_days",
            "降水1日あたりの平均降水量": "mean_precipitation_per_precipitation_day_mm",
            "最大日降水量": "max_daily_precipitation_mm",
            "年内最長連続降水": "longest_precipitation_streak_days",
        },
        value="年間降水量",
        label="ランキング指標",
    )
    ranking_top_n = mo.ui.dropdown(["3", "5", "10"], value="5", label="上位件数")
    ranking_controls = mo.hstack(
        [ranking_metric, ranking_top_n], gap=2, justify="start", wrap=True
    )
    return ranking_controls, ranking_metric, ranking_top_n


@app.cell
def _(
    COLORS,
    complete_annual,
    format_number,
    mo,
    ranking_controls,
    ranking_metric,
    ranking_top_n,
    streaks,
):
    _ranking_metric_name = ranking_metric.value
    _ranking_specs = {
        "annual_precipitation_mm": ("年間降水量", " mm", 1),
        "precipitation_days": ("降水日数", "日", 0),
        "mean_precipitation_per_precipitation_day_mm": (
            "降水1日あたりの平均降水量",
            " mm",
            1,
        ),
        "max_daily_precipitation_mm": ("最大日降水量", " mm", 1),
        "longest_precipitation_streak_days": ("年内最長連続降水", "日", 0),
    }
    _ranking_label, _ranking_unit, _ranking_digits = _ranking_specs[_ranking_metric_name]
    ranked = complete_annual.drop_nulls([_ranking_metric_name]).sort(_ranking_metric_name, descending=True).head(
        int(ranking_top_n.value)
    )
    rank_rows = "".join(
        f"<div class='rank-row'><b>{index + 1}</b><span>{int(row['year'])}年</span>"
        f"<strong>{format_number(row[_ranking_metric_name], _ranking_digits, _ranking_unit)}</strong></div>"
        for index, row in enumerate(ranked.iter_rows(named=True))
    )
    rank_html = mo.Html(
        f"""
        <style>
          .rank-board{{width:min(100%,680px);background:#fff;border:1px solid #dbe6e9;
            border-top:5px solid {COLORS['rain']};border-radius:9px;padding:10px 15px;box-sizing:border-box;}}
          .rank-row{{display:grid;grid-template-columns:32px minmax(80px,1fr) auto;align-items:center;
            gap:8px;min-height:42px;border-top:1px solid #edf2f3;}}
          .rank-row:first-child{{border:0}}.rank-row b,.rank-row strong{{color:{COLORS['rain_dark']}}}
          .rank-row strong{{font-size:16px;text-align:right;}}
        </style><div class='rank-board'>{rank_rows}</div>
        """
    )
    all_time = (
        streaks.filter(streaks["streak_type"] == "precipitation")
        .sort("streak_length", descending=True)
        .head(1)
        .row(0, named=True)
    )
    ranking_panel = mo.vstack(
        [
            mo.md("## 年間ランキング"),
            mo.md(
                "完全年だけを対象に、雨の量・頻度・強さ・続き方を順位で比べます。"
            ),
            ranking_controls,
            mo.md(f"### {_ranking_label}"),
            rank_html,
            mo.md(
                f"**全期間の年跨ぎを含む最長連続降水:** `{all_time['streak_length']}日` "
                f"（{all_time['streak_start_date']}〜{all_time['streak_end_date']}）。"
                "年内ランキングの連続日数は暦年の端で区切っています。"
            ),
        ],
        gap=2,
    )
    ranking_panel
    return


@app.cell
def _(mo):
    period_selector = mo.ui.dropdown(
        options={
            "年間": "annual",
            "梅雨期（6〜7月）": "rainy_season",
            "台風期（8〜10月）": "typhoon_season",
        },
        value="梅雨期（6〜7月）",
        label="集計期間",
    )
    period_metric = mo.ui.dropdown(
        options={
            "期間降水量": "period_precipitation_mm",
            "降水日数": "precipitation_days",
            "降水1日あたりの平均降水量": "mean_precipitation_per_precipitation_day_mm",
            "最大日降水量": "max_daily_precipitation_mm",
        },
        value="期間降水量",
        label="比較指標",
    )
    period_controls = mo.hstack(
        [period_selector, period_metric], gap=2, justify="start", wrap=True
    )
    return period_controls, period_metric, period_selector


@app.cell
def _(
    COLORS,
    alt,
    mo,
    period_controls,
    period_metric,
    period_selector,
    periods,
    pl,
    target_end,
    target_start,
):
    _period_metric_name = period_metric.value
    _period_specs = {
        "period_precipitation_mm": ("期間降水量", "mm", ",.1f"),
        "precipitation_days": ("降水日数", "日", ",.0f"),
        "mean_precipitation_per_precipitation_day_mm": (
            "降水1日あたりの平均降水量",
            "mm",
            ",.1f",
        ),
        "max_daily_precipitation_mm": ("最大日降水量", "mm", ",.1f"),
    }
    _period_metric_label, _period_unit, _period_number_format = _period_specs[_period_metric_name]
    period_view = (
        periods.filter(
            (pl.col("period_key") == period_selector.value)
            & pl.col("year").is_between(target_start, target_end)
        )
        .with_columns(
            pl.when(pl.col("is_complete_period"))
            .then(pl.lit("集計期間の観測完了"))
            .when(pl.col("observed_end_date") < pl.col("expected_end_date"))
            .then(
                pl.format(
                    "{}月{}日時点の参考値",
                    pl.col("observed_end_date").dt.month(),
                    pl.col("observed_end_date").dt.day(),
                )
            )
            .otherwise(pl.lit("欠測を含む参考値"))
            .alias("status_label")
        )
    )
    complete_periods = period_view.filter(pl.col("is_complete_period"))
    reference_periods = period_view.filter(~pl.col("is_complete_period"))
    year_axis = alt.X(
        "year:Q",
        title="年",
        axis=alt.Axis(format="d", tickCount=8, labelAngle=0, labelOverlap="greedy"),
        scale=alt.Scale(domain=[target_start - 1, target_end + 1]),
    )
    period_line = (
        alt.Chart(complete_periods)
        .mark_line(point=True, strokeWidth=2.3, color=COLORS["rain"])
        .encode(
            x=year_axis,
            y=alt.Y(f"{_period_metric_name}:Q", title=f"{_period_metric_label}（{_period_unit}）", scale=alt.Scale(zero=True)),
            tooltip=[
                alt.Tooltip("year:Q", title="年", format="d"),
                alt.Tooltip(f"{_period_metric_name}:Q", title=_period_metric_label, format=_period_number_format),
                alt.Tooltip("status_label:N", title="集計状態"),
            ],
        )
    )
    period_reference = (
        alt.Chart(reference_periods)
        .mark_point(shape="triangle-up", size=90, filled=True, color=COLORS["reference"])
        .encode(
            x=year_axis,
            y=alt.Y(f"{_period_metric_name}:Q", title=f"{_period_metric_label}（{_period_unit}）"),
            tooltip=[
                alt.Tooltip("year:Q", title="年", format="d"),
                alt.Tooltip(f"{_period_metric_name}:Q", title=f"{_period_metric_label}（参考値）", format=_period_number_format),
                alt.Tooltip("status_label:N", title="集計状態"),
            ],
        )
    )
    period_label = period_view["period_label"].head(1).item()
    period_chart = (period_line + period_reference).properties(
        title=f"{period_label}の{_period_metric_label}", width="container", height=290
    )
    period_panel = mo.vstack(
        [
            mo.md("## 固定期間で比べる"),
            mo.md(
                "任意の1か月ではなく、集計範囲を固定した「年間」「梅雨期（6〜7月）」"
                "「台風期（8〜10月）」で、雨の量・頻度・強さを長期比較します。"
                "▲は年途中または欠測を含む参考値です。"
            ),
            period_controls,
            period_chart,
        ],
        gap=2,
    )
    period_panel
    return


@app.cell
def _(mo):
    data_about = mo.accordion(
        {
            "データについて": mo.md(
                """
                - 出典は気象庁「過去の気象データ・ダウンロード」の東京（北の丸公園、地点47662）日別値です。
                - 集計値には品質コード8（正常値）の観測だけを使います。欠測・資料不足を含む年や、年途中の値は参考値として示します。
                - 「降水日数」は、気象庁の現象なし情報から降水現象があったと判断できる日数です。0.0mmでも微量の降水現象があれば含みます。
                - 「降水1日あたりの平均降水量」は `期間降水量 ÷ 降水日数` です。0.0mmでも降水現象が観測された日は分母に含めます。
                - 0.0mm超の日だけを分母にする平均値もデータ上は補助指標として保持しますが、画面の主要指標には使用しません。
                - 灰色の累積帯は、完全年の各月日における累積降水量の25〜75%点です。日降水量の分布ではありません。
                """
            )
        }
    )
    mo.vstack([mo.md("---"), data_about, mo.md("データ最終取得: 2026年10月13日")])
    return


if __name__ == "__main__":
    app.run()

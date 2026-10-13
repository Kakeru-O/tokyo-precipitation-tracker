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
        return f"通年データがそろった{valid.height}年中 {rank}位・長期平均比 {delta:+,.{digits}f}{unit}"

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
    chart_data = shown_annual
    _rainfall_top = float(chart_data["annual_precipitation_mm"].max()) * 1.08
    _days_top = float(chart_data["precipitation_days"].max()) * 1.08
    _rainfall_scale = alt.Scale(domain=[0, _rainfall_top], nice=True)
    _days_scale = alt.Scale(domain=[0, _days_top], nice=True)
    x_encoding = alt.X(
        "year:Q",
        title="年（クリックで詳細を表示）",
        axis=alt.Axis(
            format="d",
            tickCount=8,
            labelAngle=0,
            labelOverlap="greedy",
            labelPadding=6,
            titlePadding=12,
        ),
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
                axis=alt.Axis(
                    orient="left",
                    titleColor=COLORS["rain_dark"],
                    tickCount=6,
                    ticks=True,
                    labels=True,
                    domain=True,
                    format=",.0f",
                    labelPadding=5,
                    titlePadding=12,
                ),
                scale=_rainfall_scale,
            ),
            opacity=alt.condition(year_selection, alt.value(0.82), alt.value(0.25)),
            tooltip=[
                alt.Tooltip("year:Q", title="年", format="d"),
                alt.Tooltip("annual_precipitation_mm:Q", title="降水量", format=",.1f"),
                alt.Tooltip("precipitation_days:Q", title="降水日数", format=",.0f"),
            ],
        )
    )
    reference_points = (
        alt.Chart(chart_data)
        .transform_filter(
            alt.FieldEqualPredicate(field="is_complete_calendar_year", equal=False)
        )
        .mark_point(
            shape="triangle-up", size=95, filled=True, color=COLORS["rain_dark"]
        )
        .encode(
            x=x_encoding,
            y=alt.Y(
                "annual_precipitation_mm:Q",
                title=None,
                axis=None,
                scale=_rainfall_scale,
            ),
            tooltip=[
                alt.Tooltip("year:Q", title="年", format="d"),
                alt.Tooltip("annual_precipitation_mm:Q", title="参考値", format=",.1f"),
            ],
        )
    )
    days_line = (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=2.2, color=COLORS["days"])
        .encode(
            x=x_encoding,
            y=alt.Y(
                "precipitation_days:Q",
                title="降水日数（日）",
                axis=alt.Axis(
                    orient="right",
                    titleColor=COLORS["days"],
                    grid=False,
                    tickCount=6,
                    ticks=True,
                    labels=True,
                    domain=True,
                    format=",.0f",
                    labelPadding=8,
                    titlePadding=16,
                ),
                scale=_days_scale,
            ),
            tooltip=[
                alt.Tooltip("year:Q", title="年", format="d"),
                alt.Tooltip("precipitation_days:Q", title="降水日数", format=",.0f"),
                alt.Tooltip("annual_precipitation_mm:Q", title="降水量", format=",.1f"),
            ],
        )
    )
    days_reference = (
        alt.Chart(chart_data)
        .transform_filter(
            alt.FieldEqualPredicate(field="is_complete_calendar_year", equal=False)
        )
        .mark_point(
            shape="triangle-up", filled=True, size=95, color=COLORS["days"]
        )
        .encode(
            x=x_encoding,
            y=alt.Y(
                "precipitation_days:Q", title=None, axis=None, scale=_days_scale
            ),
            tooltip=[
                alt.Tooltip("year:Q", title="年", format="d"),
                alt.Tooltip(
                    "precipitation_days:Q", title="降水日数（参考値）", format=",.0f"
                ),
            ],
        )
    )
    annual_chart = (
        alt.layer(rainfall_bars, reference_points, days_line, days_reference)
        .resolve_scale(y="independent")
        .add_params(year_selection)
        .properties(
            title="年間降水量と降水日数の推移",
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
                f"`{target_start}`〜`{target_end}`年を表示（1年分の観測がそろい、比較に使える年は"
                f"`{shown_complete.height}`年）。\n\n{latest_note}"
            ),
            mo.md(
                f"<span style='color:{COLORS['rain_dark']}'><b>青い棒:</b> 年間降水量（左軸）</span>　"
                f"<span style='color:{COLORS['days']}'><b>緑の線:</b> 降水日数（右軸）</span>　"
                "▲ 年途中または欠測を含む参考値"
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
        title="年内累計降水量（灰色帯は通年データがそろった年の25〜75%点、破線は中央値）",
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
        "この年は1年分の観測がそろっているため、順位と長期平均との差を表示します。"
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
def _(complete_annual, mo):
    _comparison_years = [str(year) for year in complete_annual["year"].to_list()]
    _comparison_start = int(_comparison_years[0])
    _comparison_end = int(_comparison_years[-1])
    compare_a_start = mo.ui.dropdown(
        _comparison_years,
        value="1926" if "1926" in _comparison_years else _comparison_years[0],
        label="期間A 開始年",
    )
    compare_a_end = mo.ui.dropdown(
        _comparison_years,
        value="1955" if "1955" in _comparison_years else str(min(_comparison_start + 29, _comparison_end)),
        label="期間A 終了年",
    )
    compare_b_start = mo.ui.dropdown(
        _comparison_years,
        value="1996" if "1996" in _comparison_years else str(max(_comparison_start, _comparison_end - 29)),
        label="期間B 開始年",
    )
    compare_b_end = mo.ui.dropdown(
        _comparison_years,
        value="2025" if "2025" in _comparison_years else _comparison_years[-1],
        label="期間B 終了年",
    )
    compare_controls = mo.hstack(
        [compare_a_start, compare_a_end, compare_b_start, compare_b_end],
        gap=2,
        justify="start",
        wrap=True,
    )
    return (
        compare_a_end,
        compare_a_start,
        compare_b_end,
        compare_b_start,
        compare_controls,
    )


@app.cell
def _(
    COLORS,
    compare_a_end,
    compare_a_start,
    compare_b_end,
    compare_b_start,
    compare_controls,
    complete_annual,
    format_number,
    mo,
    pl,
    stat_cards,
):
    _a_start, _a_end = sorted((int(compare_a_start.value), int(compare_a_end.value)))
    _b_start, _b_end = sorted((int(compare_b_start.value), int(compare_b_end.value)))
    _period_a = complete_annual.filter(pl.col("year").is_between(_a_start, _a_end))
    _period_b = complete_annual.filter(pl.col("year").is_between(_b_start, _b_end))
    _label_a = f"{_a_start}〜{_a_end}年（{_period_a.height}年）"
    _label_b = f"{_b_start}〜{_b_end}年（{_period_b.height}年）"
    _comparison_specs = [
        ("年間降水量", "annual_precipitation_mm", 1, "mm"),
        ("降水日数", "precipitation_days", 1, "日"),
        ("降水1日あたりの平均降水量", "mean_precipitation_per_precipitation_day_mm", 1, "mm"),
        ("最大日降水量", "max_daily_precipitation_mm", 1, "mm"),
        ("年内最長連続降水", "longest_precipitation_streak_days", 1, "日"),
    ]
    _comparison_rows = []
    for _label, _field, _digits, _unit in _comparison_specs:
        _mean_a = _period_a[_field].mean()
        _mean_b = _period_b[_field].mean()
        _comparison_rows.append(
            (
                _label,
                format_number(_mean_a, _digits, _unit),
                format_number(_mean_b, _digits, _unit),
                f"{float(_mean_b) - float(_mean_a):+,.{_digits}f}{_unit}",
            )
        )
    _comparison_table = pl.DataFrame(
        _comparison_rows,
        schema=["指標", _label_a, _label_b, "差（B−A）"],
        orient="row",
    )
    _comparison_cards = stat_cards(
        [
            {
                "label": "年間降水量の差",
                "value": f"{float(_period_b['annual_precipitation_mm'].mean()) - float(_period_a['annual_precipitation_mm'].mean()):+,.1f} mm",
                "caption": f"{_label_a} → {_label_b}",
                "color": COLORS["rain"],
            },
            {
                "label": "降水日数の差",
                "value": f"{float(_period_b['precipitation_days'].mean()) - float(_period_a['precipitation_days'].mean()):+,.1f}日",
                "caption": "0.0mmの微量降水日を含む",
                "color": COLORS["days"],
            },
            {
                "label": "降水1日あたりの差",
                "value": f"{float(_period_b['mean_precipitation_per_precipitation_day_mm'].mean()) - float(_period_a['mean_precipitation_per_precipitation_day_mm'].mean()):+,.1f} mm",
                "caption": "各期間の年平均同士の差",
                "color": COLORS["intensity"],
            },
        ]
    )
    mo.vstack(
        [
            mo.md("## 2つの年代を比べる"),
            mo.md("1年分の観測がそろった年だけを使い、2つの期間の年平均を比較します。"),
            compare_controls,
            _comparison_cards,
            mo.ui.table(_comparison_table, pagination=False),
        ],
        gap=2,
    )
    return


@app.cell
def _(COLORS, complete_annual, format_number, mo, streaks):
    _ranking_specs = [
        ("年間降水量", "annual_precipitation_mm", " mm", 1, COLORS["rain"]),
        ("降水日数", "precipitation_days", "日", 0, COLORS["days"]),
        ("降水1日あたりの平均降水量", "mean_precipitation_per_precipitation_day_mm", " mm", 1, COLORS["intensity"]),
        ("最大日降水量", "max_daily_precipitation_mm", " mm", 1, COLORS["cumulative"]),
        ("年内最長連続降水", "longest_precipitation_streak_days", "日", 0, COLORS["reference"]),
    ]
    _ranking_boards = []
    for _label, _field, _unit, _digits, _color in _ranking_specs:
        _ranked = complete_annual.drop_nulls([_field]).sort(_field, descending=True).head(5)
        _rows = "".join(
            f"<div class='rank-row'><b>{_index + 1}</b><span>{int(_row['year'])}年</span>"
            f"<strong>{format_number(_row[_field], _digits, _unit)}</strong></div>"
            for _index, _row in enumerate(_ranked.iter_rows(named=True))
        )
        _ranking_boards.append(
            f"<section class='rank-board' style='--rank-color:{_color}'>"
            f"<h3>{_label}</h3>{_rows}</section>"
        )
    _rank_html = mo.Html(
        f"""
        <style>
          .rank-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;}}
          .rank-board{{background:#fff;border:1px solid #dbe6e9;border-top:5px solid var(--rank-color);
            border-radius:9px;padding:10px 15px;box-sizing:border-box;}}
          .rank-board h3{{font-size:16px;margin:3px 0 8px;color:#18313d;}}
          .rank-row{{display:grid;grid-template-columns:28px minmax(72px,1fr) auto;align-items:center;
            gap:8px;min-height:38px;border-top:1px solid #edf2f3;}}
          .rank-row b,.rank-row strong{{color:var(--rank-color)}}.rank-row strong{{text-align:right;}}
        </style><div class='rank-grid'>{''.join(_ranking_boards)}</div>
        """
    )
    _all_time = (
        streaks.filter(streaks["streak_type"] == "precipitation")
        .sort("streak_length", descending=True)
        .head(1)
        .row(0, named=True)
    )
    mo.vstack(
        [
            mo.md("## 年間ランキング"),
            mo.md("1年分の観測がそろった年を対象に、5つの指標の上位5年をまとめて表示します。"),
            _rank_html,
            mo.md(
                f"**全期間の年跨ぎを含む最長連続降水:** `{_all_time['streak_length']}日` "
                f"（{_all_time['streak_start_date']}〜{_all_time['streak_end_date']}）。"
                "年内ランキングの連続日数は暦年の端で区切っています。"
            ),
        ],
        gap=2,
    )
    return


@app.cell
def _(COLORS, alt, mo, periods, pl, target_end, target_start):
    _period_view = periods.filter(pl.col("year").is_between(target_start, target_end))
    _complete_periods = _period_view.filter(pl.col("is_complete_period"))
    _reference_periods = _period_view.filter(~pl.col("is_complete_period"))
    _period_domain = ["年間", "梅雨期（6〜7月）", "台風期（8〜10月）"]
    _period_colors = [COLORS["rain"], COLORS["days"], COLORS["cumulative"]]
    _fixed_period_specs = [
        ("期間降水量", "period_precipitation_mm", "mm", ",.1f"),
        ("降水日数", "precipitation_days", "日", ",.0f"),
        ("降水1日あたりの平均降水量", "mean_precipitation_per_precipitation_day_mm", "mm", ",.1f"),
        ("最大日降水量", "max_daily_precipitation_mm", "mm", ",.1f"),
    ]
    _fixed_period_charts = []
    for _label, _field, _unit, _number_format in _fixed_period_specs:
        _x = alt.X(
            "year:Q",
            title="年",
            axis=alt.Axis(format="d", tickCount=8, labelAngle=0, labelOverlap="greedy"),
            scale=alt.Scale(domain=[target_start - 1, target_end + 1]),
        )
        _color = alt.Color(
            "period_label:N",
            title=None,
            scale=alt.Scale(domain=_period_domain, range=_period_colors),
            legend=alt.Legend(orient="bottom", columns=3),
        )
        _lines = (
            alt.Chart(_complete_periods)
            .mark_line(point=True, strokeWidth=2.1)
            .encode(
                x=_x,
                y=alt.Y(f"{_field}:Q", title=f"{_label}（{_unit}）", scale=alt.Scale(zero=True)),
                color=_color,
                tooltip=[
                    alt.Tooltip("year:Q", title="年", format="d"),
                    alt.Tooltip("period_label:N", title="期間"),
                    alt.Tooltip(f"{_field}:Q", title=_label, format=_number_format),
                ],
            )
        )
        _references = (
            alt.Chart(_reference_periods)
            .mark_point(shape="triangle-up", size=80, filled=True)
            .encode(
                x=_x,
                y=alt.Y(f"{_field}:Q", title=f"{_label}（{_unit}）"),
                color=_color,
                tooltip=[
                    alt.Tooltip("year:Q", title="年", format="d"),
                    alt.Tooltip("period_label:N", title="期間"),
                    alt.Tooltip(f"{_field}:Q", title=f"{_label}（参考値）", format=_number_format),
                ],
            )
        )
        _fixed_period_charts.append(
            (_lines + _references).properties(title=_label, width="container", height=230)
        )
    mo.vstack(
        [
            mo.md("## 固定期間で比べる"),
            mo.md(
                "「年間」「梅雨期（6〜7月）」「台風期（8〜10月）」を、4つの指標ですべて表示します。"
                "▲は年途中または欠測を含む参考値です。"
            ),
            *_fixed_period_charts,
        ],
        gap=2,
    )
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
                - 灰色の累積帯は、1年分の観測がそろった年について、各月日の累積降水量を並べた25〜75%点です。日降水量の分布ではありません。
                """
            )
        }
    )
    mo.vstack([mo.md("---"), data_about, mo.md("データ最終取得: 2026年10月13日")])
    return


if __name__ == "__main__":
    app.run()

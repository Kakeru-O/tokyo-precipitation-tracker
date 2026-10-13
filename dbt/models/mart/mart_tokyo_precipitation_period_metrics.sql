with period_definitions as (
    select *
    from (values
        ('annual', '年間', 1, 1, 12, 31),
        ('rainy_season', '梅雨期（6〜7月）', 6, 1, 7, 31),
        ('typhoon_season', '台風期（8〜10月）', 8, 1, 10, 31)
    ) as definitions(
        period_key,
        period_label,
        start_month,
        start_day,
        end_month,
        end_day
    )
),
years as (
    select distinct year
    from {{ ref('int_tokyo_daily_precipitation_features') }}
),
periods as (
    select
        y.year,
        p.period_key,
        p.period_label,
        make_date(y.year, p.start_month, p.start_day) as expected_start_date,
        make_date(y.year, p.end_month, p.end_day) as expected_end_date
    from years y
    cross join period_definitions p
),
aggregated as (
    select
        p.year,
        p.period_key,
        p.period_label,
        p.expected_start_date,
        p.expected_end_date,
        min(d.observed_date) as observed_start_date,
        max(d.observed_date) as observed_end_date,
        count(d.observed_date)::int as rows_present,
        sum(case when d.is_complete_observation then 1 else 0 end)::int
            as complete_observation_days,
        sum(case when d.is_complete_observation then d.precipitation_mm end)
            as period_precipitation_mm,
        sum(case when d.is_precipitation_day then 1 else 0 end)::int
            as precipitation_days,
        sum(case when d.is_measurable_precipitation_day then 1 else 0 end)::int
            as measurable_precipitation_days,
        max(case when d.is_complete_observation then d.precipitation_mm end)
            as max_daily_precipitation_mm
    from periods p
    left join {{ ref('int_tokyo_daily_precipitation_features') }} d
      on d.year = p.year
     and d.observed_date between p.expected_start_date and p.expected_end_date
    group by 1, 2, 3, 4, 5
)

select
    *,
    (
        observed_start_date = expected_start_date
        and observed_end_date = expected_end_date
        and rows_present = date_diff('day', expected_start_date, expected_end_date) + 1
        and complete_observation_days = rows_present
    ) as is_complete_period,
    period_precipitation_mm / nullif(precipitation_days, 0)
        as mean_precipitation_per_precipitation_day_mm,
    period_precipitation_mm / nullif(measurable_precipitation_days, 0)
        as mean_precipitation_per_measurable_day_mm
from aggregated
order by period_key, year

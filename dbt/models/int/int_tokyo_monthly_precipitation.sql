select
    date_trunc('month', observed_date)::date as month_start,
    year,
    month,
    count(*)::int as rows_present,
    sum(case when is_complete_observation then 1 else 0 end)::int as complete_observation_days,
    sum(case when quality_code = 4 then 1 else 0 end)::int as insufficient_days,
    sum(case when quality_code = 2 then 1 else 0 end)::int as questionable_days,
    sum(case when quality_code = 1 then 1 else 0 end)::int as missing_days,
    sum(case when is_complete_observation then precipitation_mm end) as precipitation_mm,
    sum(case when is_precipitation_day then 1 else 0 end)::int as precipitation_days,
    sum(case when is_measurable_precipitation_day then 1 else 0 end)::int
        as measurable_precipitation_days,
    sum(case when is_no_precipitation_day then 1 else 0 end)::int as no_precipitation_days,
    sum(case when is_complete_observation then precipitation_mm end)
        / nullif(sum(case when is_precipitation_day then 1 else 0 end), 0)
        as mean_precipitation_per_phenomenon_day_mm,
    sum(case when is_complete_observation then precipitation_mm end)
        / nullif(sum(case when is_precipitation_day then 1 else 0 end), 0)
        as mean_precipitation_per_precipitation_day_mm,
    sum(case when is_complete_observation then precipitation_mm end)
        / nullif(sum(case when is_measurable_precipitation_day then 1 else 0 end), 0)
        as mean_precipitation_per_measurable_day_mm,
    max(case when is_complete_observation then precipitation_mm end) as max_daily_precipitation_mm
from {{ ref('int_tokyo_daily_precipitation_features') }}
group by 1, 2, 3

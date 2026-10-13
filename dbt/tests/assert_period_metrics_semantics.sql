select *
from {{ ref('mart_tokyo_precipitation_period_metrics') }}
where (period_key = 'rainy_season'
       and date_diff('day', expected_start_date, expected_end_date) + 1 <> 61)
   or (period_key = 'typhoon_season'
       and date_diff('day', expected_start_date, expected_end_date) + 1 <> 92)
   or (
       precipitation_days > 0
       and abs(
           mean_precipitation_per_precipitation_day_mm
           - period_precipitation_mm / precipitation_days
       ) > 0.000001
   )
   or (
       measurable_precipitation_days > 0
       and abs(
           mean_precipitation_per_measurable_day_mm
           - period_precipitation_mm / measurable_precipitation_days
       ) > 0.000001
   )
   or (year = 2026 and period_key = 'rainy_season' and not is_complete_period)
   or (year = 2026 and period_key = 'typhoon_season' and is_complete_period)

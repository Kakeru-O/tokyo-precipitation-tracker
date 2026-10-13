select
    observed_date,
    year,
    month,
    day,
    dayofyear,
    precipitation_mm,
    precipitation_mm_raw,
    has_precipitation_phenomenon,
    is_precipitation_day,
    is_measurable_precipitation_day,
    is_no_precipitation_day,
    quality_code,
    quality_status,
    cumulative_precipitation_mm,
    cumulative_precipitation_days,
    source_file
from {{ ref('int_tokyo_daily_precipitation_features') }}
order by observed_date

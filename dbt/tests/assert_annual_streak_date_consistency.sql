with annual_streaks as (
    select
        year,
        'precipitation' as streak_type,
        longest_precipitation_streak_days as streak_days,
        longest_precipitation_streak_start_date as streak_start_date,
        longest_precipitation_streak_end_date as streak_end_date
    from {{ ref('mart_tokyo_precipitation_annual_metrics') }}

    union all

    select
        year,
        'no_precipitation' as streak_type,
        longest_no_precipitation_streak_days as streak_days,
        longest_no_precipitation_streak_start_date as streak_start_date,
        longest_no_precipitation_streak_end_date as streak_end_date
    from {{ ref('mart_tokyo_precipitation_annual_metrics') }}
)

select *
from annual_streaks
where (streak_days is null) <> (streak_start_date is null)
   or (streak_days is null) <> (streak_end_date is null)
   or streak_days <> date_diff('day', streak_start_date, streak_end_date) + 1
   or extract(year from streak_start_date) <> year
   or extract(year from streak_end_date) <> year

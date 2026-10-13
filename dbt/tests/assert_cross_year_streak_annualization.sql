with expected as (
    select
        1956::int as year,
        22::int as longest_no_precipitation_streak_days,
        date '1956-12-10' as longest_no_precipitation_streak_start_date,
        date '1956-12-31' as longest_no_precipitation_streak_end_date
)

select expected.*
from expected
left join {{ ref('mart_tokyo_precipitation_annual_metrics') }} as actual
    on actual.year = expected.year
where actual.year is null
   or actual.longest_no_precipitation_streak_days
      <> expected.longest_no_precipitation_streak_days
   or actual.longest_no_precipitation_streak_start_date
      <> expected.longest_no_precipitation_streak_start_date
   or actual.longest_no_precipitation_streak_end_date
      <> expected.longest_no_precipitation_streak_end_date

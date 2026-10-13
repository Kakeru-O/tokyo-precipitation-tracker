with expected as (
    select
        'precipitation'::varchar as streak_type,
        date '2026-08-27' as streak_start_date,
        date '2026-10-02' as streak_end_date,
        37::int as streak_length
)

select expected.*
from expected
where (
    select count(*)
    from {{ ref('int_tokyo_precipitation_streaks') }} as actual
    where actual.streak_type = expected.streak_type
      and actual.streak_start_date = expected.streak_start_date
      and actual.streak_end_date = expected.streak_end_date
      and actual.streak_length = expected.streak_length
) <> 1

select *
from {{ ref('int_tokyo_precipitation_streaks') }}
where streak_type = 'precipitation'
qualify row_number() over (order by streak_length desc, streak_start_date) = 1
  and not (
      streak_length = 37
      and streak_start_date = date '2026-08-27'
      and streak_end_date = date '2026-10-02'
  )

with annual as (
    select * from {{ ref('int_tokyo_annual_precipitation') }}
),
overlapping_streaks as (
    select
        a.year,
        s.streak_type,
        greatest(s.streak_start_date, make_date(a.year, 1, 1))
            as annual_streak_start_date,
        least(s.streak_end_date, make_date(a.year, 12, 31))
            as annual_streak_end_date,
        date_diff(
            'day',
            greatest(s.streak_start_date, make_date(a.year, 1, 1)),
            least(s.streak_end_date, make_date(a.year, 12, 31))
        )::int + 1 as annual_streak_length,
        row_number() over (
            partition by a.year, s.streak_type
            order by
                annual_streak_length desc,
                annual_streak_start_date
        ) as rank_in_year
    from annual a
    join {{ ref('int_tokyo_precipitation_streaks') }} s
      on s.streak_start_date <= make_date(a.year, 12, 31)
     and s.streak_end_date >= make_date(a.year, 1, 1)
),
longest as (
    select
        year,
        max(case when streak_type = 'precipitation' then annual_streak_length end)
            as longest_precipitation_streak_days,
        max(case when streak_type = 'precipitation' then annual_streak_start_date end)
            as longest_precipitation_streak_start_date,
        max(case when streak_type = 'precipitation' then annual_streak_end_date end)
            as longest_precipitation_streak_end_date,
        max(case when streak_type = 'no_precipitation' then annual_streak_length end)
            as longest_no_precipitation_streak_days,
        max(case when streak_type = 'no_precipitation' then annual_streak_start_date end)
            as longest_no_precipitation_streak_start_date,
        max(case when streak_type = 'no_precipitation' then annual_streak_end_date end)
            as longest_no_precipitation_streak_end_date
    from overlapping_streaks
    where rank_in_year = 1
    group by 1
)

select a.*, l.* exclude (year)
from annual a
left join longest l using (year)
order by year

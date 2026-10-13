with classified as (
    select
        observed_date,
        case
            when is_precipitation_day then 'precipitation'
            when is_no_precipitation_day then 'no_precipitation'
            else 'unknown'
        end as streak_type
    from {{ ref('int_tokyo_daily_precipitation_features') }}
),
boundaries as (
    select
        *,
        case
            when lag(observed_date) over (order by observed_date) is null then 1
            when observed_date - lag(observed_date) over (order by observed_date) <> 1 then 1
            when streak_type <> lag(streak_type) over (order by observed_date) then 1
            else 0
        end as starts_new_streak
    from classified
),
islands as (
    select
        *,
        sum(starts_new_streak) over (order by observed_date rows unbounded preceding) as streak_id
    from boundaries
)

select
    streak_type,
    streak_id,
    min(observed_date) as streak_start_date,
    max(observed_date) as streak_end_date,
    count(*)::int as streak_length
from islands
where streak_type <> 'unknown'
group by 1, 2

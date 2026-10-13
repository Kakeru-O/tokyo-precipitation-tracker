with daily as (
    select * from {{ ref('stg_jma_tokyo_daily_precipitation') }}
),
features as (
    select
        *,
        (quality_code = 8) as is_complete_observation,
        (quality_code in (5, 8)) as is_usable_observation,
        case when quality_code = 8 then has_precipitation_phenomenon end
            as is_precipitation_day,
        case when quality_code = 8 and precipitation_mm is not null
            then precipitation_mm > 0 end as is_measurable_precipitation_day,
        case when quality_code = 8 then not has_precipitation_phenomenon end
            as is_no_precipitation_day
    from daily
)

select
    *,
    sum(case when is_complete_observation then precipitation_mm end) over (
        partition by year order by observed_date rows unbounded preceding
    ) as cumulative_precipitation_mm,
    sum(case when is_precipitation_day then 1 else 0 end) over (
        partition by year order by observed_date rows unbounded preceding
    )::int as cumulative_precipitation_days
from features

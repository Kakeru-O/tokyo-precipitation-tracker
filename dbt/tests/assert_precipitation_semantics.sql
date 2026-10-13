select *
from {{ ref('stg_jma_tokyo_daily_precipitation') }}
where (has_precipitation_phenomenon = false and precipitation_mm <> 0)
   or (precipitation_mm > 0 and has_precipitation_phenomenon is not true)
   or (
       quality_code in (4, 5, 8)
       and (precipitation_mm is null or has_precipitation_phenomenon is null)
   )
   or (
       quality_code in (0, 1, 2)
       and (precipitation_mm is not null or has_precipitation_phenomenon is not null)
   )

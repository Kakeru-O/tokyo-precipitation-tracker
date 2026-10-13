select *
from {{ ref('mart_tokyo_precipitation_annual_metrics') }}
where precipitation_days < measurable_precipitation_days
   or (
       precipitation_days > 0
       and abs(
           mean_precipitation_per_precipitation_day_mm
           - annual_precipitation_mm / precipitation_days
       ) > 0.000001
   )
   or (
       measurable_precipitation_days > 0
       and abs(
           mean_precipitation_per_measurable_day_mm
           - annual_precipitation_mm / measurable_precipitation_days
       ) > 0.000001
   )

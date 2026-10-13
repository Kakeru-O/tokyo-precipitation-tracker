select year, period_key, count(*) as row_count
from {{ ref('mart_tokyo_precipitation_period_metrics') }}
group by 1, 2
having count(*) <> 1

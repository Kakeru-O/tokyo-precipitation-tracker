select *
from {{ ref('int_tokyo_monthly_precipitation') }}
order by month_start

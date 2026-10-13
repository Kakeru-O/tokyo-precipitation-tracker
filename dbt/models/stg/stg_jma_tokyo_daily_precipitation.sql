with source as (
    select *
    from read_csv_auto(
        '{{ var("processed_jma_tokyo_glob") }}',
        header=true,
        union_by_name=true,
        all_varchar=true
    )
)

select
    date::date as observed_date,
    extract(year from date::date)::int as year,
    extract(month from date::date)::int as month,
    extract(day from date::date)::int as day,
    extract(doy from date::date)::int as dayofyear,
    precipitation_mm::double as precipitation_mm,
    precipitation_mm_raw::varchar as precipitation_mm_raw,
    phenomenon_none_code::tinyint as phenomenon_none_code,
    case
        when phenomenon_none_code = 0 then true
        when phenomenon_none_code = 1 then false
    end as has_precipitation_phenomenon,
    quality_code::tinyint as quality_code,
    case quality_code
        when 8 then 'normal'
        when 5 then 'quasi_normal'
        when 4 then 'insufficient'
        when 2 then 'questionable'
        when 1 then 'missing'
        when 0 then 'not_applicable'
        else 'unknown'
    end as quality_status,
    homogeneity_number::smallint as homogeneity_number,
    source_file::varchar as source_file
from source

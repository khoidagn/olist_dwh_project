with date_series as (
    select
        datum as full_date
    from
        unnest(generate_date_array('2016-01-01', '2018-12-31', interval 1 day)) as datum
)

select
    cast(format_date('%Y%m%d', full_date) as int64) as date_key,
    full_date,
    extract(year from full_date) as year,
    extract(quarter from full_date) as quarter,
    extract(month from full_date) as month,
    format_date('%B', full_date) as month_name,
    extract(day from full_date) as day,
    extract(dayofweek from full_date) as day_of_week,
    format_date('%A', full_date) as day_name,
    case 
        when extract(dayofweek from full_date) in (1, 7) then true 
        else false 
    end as is_weekend
from date_series
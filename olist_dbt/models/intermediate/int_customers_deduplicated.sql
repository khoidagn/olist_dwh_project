with customers as (
    select * from {{ ref('stg_customers') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by customer_unique_id 
            order by customer_id desc
        ) as rn
    from customers
)

select
    customer_unique_id,
    customer_id as representative_customer_id,
    customer_city,
    customer_state,
    customer_zip_code_prefix
from ranked
where rn = 1
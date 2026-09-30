with customers as (
    select * from {{ ref('stg_customers') }}
),

orders as (
    select customer_id, order_purchase_timestamp 
    from {{ ref('stg_orders') }}
),

ranked as (
    select
        c.customer_unique_id,
        c.customer_id,
        c.customer_city,
        c.customer_state,
        c.customer_zip_code_prefix,
        row_number() over (
            partition by c.customer_unique_id 
            order by o.order_purchase_timestamp desc, c.customer_id desc
        ) as rn
    from customers c
    left join orders o on c.customer_id = o.customer_id
)

select
    customer_unique_id,
    customer_id,
    customer_city,
    customer_state,
    customer_zip_code_prefix
from ranked
where rn = 1
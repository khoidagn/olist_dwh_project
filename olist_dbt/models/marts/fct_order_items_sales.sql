with order_items as (
    select * from {{ ref('stg_order_items') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
)

select
    oi.order_id,
    oi.order_item_id,
    o.customer_id,
    c.customer_unique_id,
    oi.product_id,
    oi.seller_id,
    cast(format_date('%Y%m%d', date(o.order_purchase_timestamp)) as int64) as order_date_key,
    o.order_purchase_timestamp,
    o.order_status,
    oi.price,
    oi.freight_value,
    (oi.price + oi.freight_value) as item_total_amount
from order_items oi
inner join orders o 
    on oi.order_id = o.order_id
inner join customers c 
    on o.customer_id = c.customer_id
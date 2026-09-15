with order_items as (
    select * from {{ ref('stg_order_items') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

payments as (
    select * from {{ ref('int_order_payments_aggregated') }}
)

select
    concat(cast(oi.order_id as string), '_', cast(oi.order_item_id as string)) as order_item_key,
    oi.order_id,
    oi.order_item_id,
    o.customer_id,
    oi.product_id,
    oi.seller_id,
    cast(format_date('%Y%m%d', date(o.order_purchase_timestamp)) as int64) as order_date_key,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    oi.price,
    oi.freight_value,
    (oi.price + oi.freight_value) as item_total_amount,
    p.primary_payment_type,
    p.max_installments
from order_items oi
inner join orders o on oi.order_id = o.order_id
left join payments p on oi.order_id = p.order_id

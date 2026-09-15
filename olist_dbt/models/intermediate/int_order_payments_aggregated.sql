with payments as (
    select * from {{ ref('stg_order_payments') }}
)

select
    order_id,
    count(payment_sequential) as payment_installments_count,
    max(payment_installments) as max_installments,
    sum(payment_value) as total_payment_value,
    -- Lấy phương thức thanh toán có giá trị cao nhất trong đơn
    array_agg(payment_type order by payment_value desc)[offset(0)] as primary_payment_type
from payments
group by order_id
with payments_agg as (
    select * from {{ ref('int_order_payments_aggregated') }}
)

select
    order_id,
    primary_payment_type as payment_type_primary,
    max_installments,
    total_payment_value
from payments_agg
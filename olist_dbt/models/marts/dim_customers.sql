with customers as (
    select * from {{ ref('int_customers_deduplicated') }}
)

select
    customer_unique_id,
    customer_id,
    customer_city,
    customer_state,
    customer_zip_code_prefix
from customers
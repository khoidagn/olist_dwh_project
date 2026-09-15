with sellers as (
    select * from {{ ref('stg_sellers') }}
)

select
    seller_id,
    seller_city,
    seller_state,
    seller_zip_code_prefix
from sellers

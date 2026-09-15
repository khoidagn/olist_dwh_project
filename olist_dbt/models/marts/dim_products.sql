with products as (
    select * from {{ ref('int_products_enriched') }}
)

select
    product_id,
    product_category_name_english,
    product_name_length,
    product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm
from products
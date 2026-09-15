with products as (
    select * from {{ ref('stg_products') }}
),

translations as (
    select * from {{ source('olist_raw', 'category_name_translation') }}
)

select
    p.product_id,
    coalesce(t.string_field_1, p.product_category_name, 'others') as product_category_name_english,
    p.product_name_length,
    p.product_description_length,
    p.product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm
from products p
left join translations t 
    on p.product_category_name = t.string_field_0
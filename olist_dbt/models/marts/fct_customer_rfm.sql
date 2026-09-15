with customer_orders as (
    select
        c.customer_unique_id,
        f.order_id,
        f.order_purchase_timestamp,
        f.item_total_amount
    from {{ ref('fct_orders_sales') }} f
    inner join {{ ref('stg_customers') }} c 
        on f.customer_id = c.customer_id
    where f.order_status not in ('canceled', 'unavailable')
),

reference_date as (
    -- Lấy mốc thời gian lớn nhất trong dữ liệu cộng thêm 1 ngày để tính Recency
    select date_add(date(max(order_purchase_timestamp)), interval 1 day) as max_date
    from customer_orders
),

customer_metrics as (
    select
        co.customer_unique_id,
        date_diff(max(ref.max_date), date(max(co.order_purchase_timestamp)), day) as recency_days,
        count(distinct co.order_id) as frequency_orders,
        sum(co.item_total_amount) as monetary_value,
        max(co.order_purchase_timestamp) as last_purchase_timestamp
    from customer_orders co
    cross join reference_date ref
    group by co.customer_unique_id
),

rfm_scoring as (
    select
        customer_unique_id,
        recency_days,
        frequency_orders,
        monetary_value,
        last_purchase_timestamp,
        -- R Score: Gần đây mua hàng hơn -> Điểm cao hơn (5 = mới mua, 1 = đã lâu)
        ntile(5) over (order by recency_days desc) as r_score,
        -- F Score: Với Olist đa phần mua 1 lần, phân tầng theo số đơn
        case 
            when frequency_orders >= 4 then 5
            when frequency_orders = 3 then 4
            when frequency_orders = 2 then 3
            else 1
        end as f_score,
        -- M Score: Chi tiêu càng nhiều -> Điểm cao hơn
        ntile(5) over (order by monetary_value asc) as m_score
    from customer_metrics
),

rfm_segmented as (
    select
        customer_unique_id,
        recency_days,
        frequency_orders,
        monetary_value,
        last_purchase_timestamp,
        r_score,
        f_score,
        m_score,
        concat(cast(r_score as string), cast(f_score as string), cast(m_score as string)) as rfm_code,
        -- Phân nhóm khách hàng chuẩn e-commerce
        case
            when r_score >= 4 and f_score >= 4 then 'Champions'
            when r_score >= 3 and f_score >= 3 then 'Loyal Customers'
            when r_score >= 4 and f_score <= 2 then 'Promising / New Customers'
            when r_score = 3 and f_score <= 2 then 'Potential Loyalists'
            when r_score = 2 and f_score >= 2 then 'At Risk / Need Attention'
            when r_score <= 2 and f_score <= 2 then 'Lost / Hibernating'
            else 'About to Sleep'
        end as customer_segment,
        -- Định nghĩa Churn: Khách hàng không có đơn hàng mới trong vòng 180 ngày
        case 
            when recency_days > 180 then true 
            else false 
        end as is_churn
    from rfm_scoring
)

select * from rfm_segmented
from dataclasses import replace
from datetime import date
from utils.bigquery import table
from utils.filters import Filters


def sales_cte() -> str:
    return f"""
    sales as (
        select
            f.order_id,
            f.order_item_id,
            f.price,
            f.freight_value,
            f.item_total_amount,
            f.order_status,
            f.order_purchase_timestamp,
            f.order_delivered_customer_date,
            f.order_estimated_delivery_date,
            coalesce(pay.payment_type_primary, 'unknown') as payment_type,
            t.full_date,
            t.year,
            t.quarter,
            t.month,
            t.day_of_week,
            t.day_name,
            c.customer_unique_id,
            c.customer_state,
            c.customer_city,
            p.product_id,
            p.product_category_name_english as category,
            s.seller_state
        from {table('fct_order_items_sales')} f
        join {table('dim_time')} t on f.order_date_key = t.date_key
        join {table('dim_customers')} c on f.customer_unique_id = c.customer_unique_id
        join {table('dim_products')} p on f.product_id = p.product_id
        join {table('dim_sellers')} s on f.seller_id = s.seller_id
        left join {table('dim_payments')} pay on f.order_id = pay.order_id
        where f.order_status not in ('canceled', 'unavailable')
          and t.full_date between @start and @end
          and (coalesce(array_length(@states), 0) = 0 or c.customer_state in unnest(@states))
          and (coalesce(array_length(@categories), 0) = 0 or p.product_category_name_english in unnest(@categories))
    )"""


def _sales(select: str, f: Filters):
    return f"with {sales_cte()} {select}", f.params()


def kpi_compare(f: Filters):
    prev = f.previous()
    wide = replace(f, start=prev.start) if prev else f
    sql, params = _sales(
        """
        select
            count(distinct if(full_date >= @cur_start, order_id, null)) as orders,
            cast(sum(if(full_date >= @cur_start, item_total_amount, 0)) as float64) as revenue,
            cast(sum(if(full_date >= @cur_start, freight_value, 0)) as float64) as freight,
            count(distinct if(full_date >= @cur_start, customer_unique_id, null)) as customers,
            count(distinct if(full_date < @cur_start, order_id, null)) as prev_orders,
            cast(sum(if(full_date < @cur_start, item_total_amount, 0)) as float64) as prev_revenue,
            cast(sum(if(full_date < @cur_start, freight_value, 0)) as float64) as prev_freight,
            count(distinct if(full_date < @cur_start, customer_unique_id, null)) as prev_customers
        from sales
        """,
        wide,
    )
    return sql, params + (("cur_start", "DATE", f.start),)


def revenue_by_month(f: Filters):
    return _sales(
        """
        select
            cast(date_trunc(full_date, month) as datetime) as month,
            cast(sum(item_total_amount) as float64) as revenue,
            count(distinct order_id) as orders
        from sales
        group by month
        order by month
        """,
        f,
    )


def sales_by_category(f: Filters):
    return _sales(
        """
        select
            category,
            cast(sum(item_total_amount) as float64) as revenue,
            count(distinct order_id) as orders
        from sales
        group by category
        """,
        f,
    )


def top_products(f: Filters, limit: int = 10):
    return _sales(
        f"""
        select
            product_id,
            any_value(category) as category,
            cast(sum(item_total_amount) as float64) as revenue,
            count(distinct order_id) as orders,
            cast(avg(price) as float64) as avg_price
        from sales
        group by product_id
        order by revenue desc
        limit {int(limit)}
        """,
        f,
    )


def payment_mix(f: Filters):
    return _sales(
        """
        select payment_type, count(distinct order_id) as orders
        from sales
        group by payment_type
        order by orders desc
        """,
        f,
    )
ORDER_LEVEL = """
, order_level as (
    select
        order_id,
        any_value(customer_state) as customer_state,
        any_value(customer_city) as customer_city,
        any_value(order_purchase_timestamp) as purchased_at,
        any_value(order_delivered_customer_date) as delivered_at,
        any_value(order_estimated_delivery_date) as estimated_at,
        any_value(order_status) = 'delivered'
            and any_value(order_delivered_customer_date) is not null as is_delivered,
        sum(item_total_amount) as revenue,
        sum(price) as price,
        sum(freight_value) as freight
    from sales
    group by order_id
)
"""


def sales_by_period(f: Filters, grain: str):
    if grain not in ("month", "quarter"):
        raise ValueError(grain)
    return _sales(
        f"""
        select
            cast(date_trunc(full_date, {grain}) as datetime) as period,
            cast(sum(item_total_amount) as float64) as revenue,
            count(distinct order_id) as orders
        from sales
        group by period
        order by period
        """,
        f,
    )


def same_months_by_year(f: Filters):
    both_years = replace(f, start=date(2017, 1, 1), end=date(2018, 8, 31))
    return _sales(
        """
        select
            year,
            month,
            cast(sum(item_total_amount) as float64) as revenue,
            count(distinct order_id) as orders
        from sales
        where month <= 8
        group by year, month
        order by year, month
        """,
        both_years,
    )


def orders_by_weekday_hour(f: Filters):
    return _sales(
        """
        select
            day_of_week,
            extract(hour from order_purchase_timestamp) as hour,
            count(distinct order_id) as orders
        from sales
        group by day_of_week, hour
        """,
        f,
    )


def state_summary(f: Filters):
    return _sales(
        ORDER_LEVEL
        + """
        select
            customer_state as state,
            count(*) as orders,
            cast(sum(revenue) as float64) as revenue,
            cast(sum(revenue) / count(*) as float64) as aov,
            cast(safe_divide(sum(freight), sum(price)) as float64) as freight_ratio,
            countif(is_delivered) as delivered_orders,
            safe_divide(
                countif(is_delivered and date(delivered_at) > date(estimated_at)),
                countif(is_delivered)
            ) as late_rate,
            avg(if(is_delivered, date_diff(date(delivered_at), date(purchased_at), day), null))
                as delivery_days
        from order_level
        group by state
        """,
        f,
    )


def top_cities(f: Filters, limit: int = 10):
    return _sales(
        ORDER_LEVEL
        + f"""
        select
            customer_city as city,
            customer_state as state,
            count(*) as orders,
            cast(sum(revenue) as float64) as revenue
        from order_level
        group by city, state
        order by orders desc
        limit {int(limit)}
        """,
        f,
    )


def rfm_cte() -> str:
    return f"""
    customers as (
        select
            r.*,
            c.customer_state,
            c.customer_city
        from {table('fct_customer_rfm')} r
        join {table('dim_customers')} c using (customer_unique_id)
        where coalesce(array_length(@states), 0) = 0 or c.customer_state in unnest(@states)
    )"""


def _rfm(select: str, f: Filters, extra: tuple = ()):
    return f"with {rfm_cte()} {select}", (("states", "STRING", f.states),) + extra


def rfm_overview(f: Filters):
    return _rfm(
        f"""
        select
            count(*) as customers,
            safe_divide(countif(frequency_orders >= 2), count(*)) as repeat_rate,
            approx_quantiles(recency_days, 2)[offset(1)] as median_recency,
            cast(avg(monetary_value) as float64) as avg_monetary,
            avg(cast(is_churn as int64)) as churn_rate,
            countif(not is_churn) as active,
            countif(recency_days between 91 and 180) as cooling,
            cast(sum(if(recency_days between 91 and 180, monetary_value, 0)) as float64) as cooling_value,
            (select date(max(last_purchase_timestamp)) from {table('fct_customer_rfm')}) as last_purchase
        from customers
        """,
        f,
    )


def rfm_segments(f: Filters):
    return _rfm(
        """
        select
            customer_segment as segment,
            count(*) as customers,
            cast(sum(monetary_value) as float64) as revenue,
            avg(recency_days) as recency,
            avg(frequency_orders) as frequency,
            cast(avg(monetary_value) as float64) as monetary,
            avg(cast(is_churn as int64)) as churn_rate
        from customers
        group by segment
        """,
        f,
    )


def rfm_matrix(f: Filters):
    return _rfm(
        """
        select r_score, f_score, count(*) as customers
        from customers
        group by r_score, f_score
        """,
        f,
    )


def rfm_sample(f: Filters):
    return _rfm(
        """
        select
            recency_days,
            cast(monetary_value as float64) as monetary,
            customer_segment as segment
        from customers
        where mod(abs(farm_fingerprint(customer_unique_id)), 20) = 0
        """,
        f,
    )


def segment_customers(f: Filters, segment: str, limit: int = 500):
    return _rfm(
        f"""
        select
            customer_unique_id,
            customer_state,
            customer_city,
            recency_days,
            frequency_orders,
            cast(monetary_value as float64) as monetary,
            rfm_code
        from customers
        where customer_segment = @segment
        order by monetary desc
        limit {int(limit)}
        """,
        f,
        (("segment", "STRING", segment),),
    )

RECENCY_BUCKET = "div(recency_days - 1, 30) * 30 + 1"


def recency_histogram(f: Filters):
    return _rfm(
        f"""
        select
            {RECENCY_BUCKET} as bucket,
            count(*) as customers,
            cast(sum(monetary_value) as float64) as monetary
        from customers
        group by bucket
        order by bucket
        """,
        f,
    )


def churn_by_state(f: Filters):
    return _rfm(
        """
        select
            customer_state as state,
            count(*) as customers,
            avg(cast(is_churn as int64)) as churn_rate
        from customers
        group by state
        """,
        f,
    )


def churn_by_last_category(f: Filters, limit: int = 15):
    return _rfm(
        f"""
        , last_item as (
            select f.customer_unique_id, p.product_category_name_english as category
            from {table('fct_order_items_sales')} f
            join {table('dim_products')} p on f.product_id = p.product_id
            where f.order_status not in ('canceled', 'unavailable')
            qualify row_number() over (
                partition by f.customer_unique_id
                order by f.order_purchase_timestamp desc, f.price desc
            ) = 1
        )
        select
            l.category,
            count(*) as customers,
            avg(cast(c.is_churn as int64)) as churn_rate
        from customers c
        join last_item l using (customer_unique_id)
        group by l.category
        order by customers desc
        limit {int(limit)}
        """,
        f,
    )


def cooling_customers(f: Filters, limit: int = 500):
    return _rfm(
        f"""
        select
            customer_unique_id,
            customer_state,
            customer_segment as segment,
            recency_days,
            frequency_orders,
            cast(monetary_value as float64) as monetary
        from customers
        where recency_days between 91 and 180
        order by monetary desc
        limit {int(limit)}
        """,
        f,
    )


def campaign_pool(f: Filters):
    return _rfm(
        f"""
        select
            customer_segment as segment,
            customer_state as state,
            {RECENCY_BUCKET} as bucket,
            count(*) as customers,
            sum(frequency_orders) as orders,
            countif(frequency_orders >= 2) as repeaters,
            cast(sum(monetary_value) as float64) as monetary
        from customers
        group by segment, state, bucket
        """,
        f,
    )


def campaign_targets(f: Filters, rmin: int, rmax: int, segments: tuple, limit: int = 1000):
    return _rfm(
        f"""
        select
            customer_unique_id,
            customer_state,
            customer_city,
            customer_segment as segment,
            recency_days,
            frequency_orders,
            cast(monetary_value as float64) as monetary
        from customers
        where recency_days between @rmin and @rmax
          and customer_segment in unnest(@segments)
        order by monetary desc
        limit {int(limit)}
        """,
        f,
        (("rmin", "INT64", int(rmin)), ("rmax", "INT64", int(rmax)), ("segments", "STRING", tuple(segments))),
    )


def data_end():
    return (
        f"select date(max(last_purchase_timestamp)) as last_date from {table('fct_customer_rfm')}",
        (),
    )

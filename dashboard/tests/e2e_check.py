import sys
import time
import tomllib
import warnings
from datetime import date
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))
warnings.filterwarnings("ignore")

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

from utils.bigquery import _job_config
from utils.filters import MAX_DATE, MIN_DATE, Filters
from utils import queries as Q

CFG = tomllib.loads((APP_DIR / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["bigquery"]
CREDS = service_account.Credentials.from_service_account_file(str((APP_DIR / CFG["key_path"]).resolve()))
CLIENT = bigquery.Client(credentials=CREDS, project=CFG["project"], location=CFG["location"])
RAW = f"`{CFG['project']}.raw_layer"
MART = f"`{CFG['project']}.{CFG['dataset']}"
VALID = "o.order_status not in ('canceled', 'unavailable')"
ALL = Filters(MIN_DATE, MAX_DATE, (), ())
results = []


def run(spec) -> pd.DataFrame:
    sql, params = spec if isinstance(spec, tuple) else (spec, ())
    job = CLIENT.query(sql, job_config=_job_config(params, True))
    return job.to_dataframe(create_bqstorage_client=False)


def one(spec) -> pd.Series:
    return run(spec).iloc[0]


def check(group: str, name: str, expected, actual, tol: float = 0.0) -> None:
    ok = abs(float(expected) - float(actual)) <= tol
    results.append({"Nhóm": group, "Kiểm tra": name, "Kỳ vọng": expected, "Thực tế": actual, "Kết quả": "PASS" if ok else "FAIL"})


def raw_sources() -> str:
    return f"""
    o as (
        select order_id, customer_id, order_status,
               safe_cast(order_purchase_timestamp as timestamp) as purchased_at
        from {RAW}.orders` o
    ),
    i as (
        select order_id, order_item_id,
               safe_cast(price as float64) as price,
               safe_cast(freight_value as float64) as freight
        from {RAW}.order_items`
    ),
    c as (select customer_id, customer_unique_id from {RAW}.customers`)
    """


def pipeline_checks() -> None:
    raw = one(f"""
        with {raw_sources()}
        select count(*) as rows_, sum(i.price + i.freight) as amount
        from i join o using (order_id)
    """)
    fact = one(f"""
        select count(*) as rows_,
               cast(sum(item_total_amount) as float64) as amount,
               count(distinct concat(order_id, '-', cast(order_item_id as string))) as grain
        from {MART}.fct_order_items_sales`
    """)
    check("CSV → DWH", "Số dòng fact = số dòng order_items gốc", raw["rows_"], fact["rows_"])
    check("CSV → DWH", "Tổng price + freight của fact = dữ liệu gốc", round(raw["amount"], 2), round(fact["amount"], 2), 0.5)
    check("CSV → DWH", "Fact không trùng (order_id, order_item_id)", fact["rows_"], fact["grain"])

    raw_cust = one(f"select count(distinct customer_unique_id) as n from {RAW}.customers`")["n"]
    dim_cust = one(f"select count(*) as n from {MART}.dim_customers`")["n"]
    check("CSV → DWH", "dim_customers = số customer_unique_id gốc", raw_cust, dim_cust)


def dashboard_checks() -> pd.Series:
    raw = one(f"""
        with {raw_sources()}
        select count(distinct o.order_id) as orders,
               sum(i.price + i.freight) as revenue,
               sum(i.freight) as freight,
               count(distinct c.customer_unique_id) as customers
        from i join o using (order_id) join c using (customer_id)
        where {VALID}
    """)
    kpi = run(Q.kpi_compare(ALL)).fillna(0).iloc[0]
    check("DWH → Dashboard", "KPI số đơn = tính từ dữ liệu gốc", raw["orders"], kpi["orders"])
    check("DWH → Dashboard", "KPI doanh thu = tính từ dữ liệu gốc", round(raw["revenue"], 2), round(kpi["revenue"], 2), 0.5)
    check("DWH → Dashboard", "KPI phí vận chuyển = tính từ dữ liệu gốc", round(raw["freight"], 2), round(kpi["freight"], 2), 0.5)
    check("DWH → Dashboard", "KPI số khách = tính từ dữ liệu gốc", raw["customers"], kpi["customers"])

    month = run(Q.sales_by_period(ALL, "month"))
    quarter = run(Q.sales_by_period(ALL, "quarter"))
    cats = run(Q.sales_by_category(ALL))
    pays = run(Q.payment_mix(ALL))
    states = run(Q.state_summary(ALL))
    total = round(kpi["revenue"], 2)
    check("Nhất quán giữa biểu đồ", "Tổng doanh thu theo tháng = KPI", total, round(month["revenue"].sum(), 2), 0.5)
    check("Nhất quán giữa biểu đồ", "Tổng doanh thu theo quý = KPI", total, round(quarter["revenue"].sum(), 2), 0.5)
    check("Nhất quán giữa biểu đồ", "Tổng doanh thu theo danh mục = KPI", total, round(cats["revenue"].sum(), 2), 0.5)
    check("Nhất quán giữa biểu đồ", "Tổng doanh thu theo bang = KPI", total, round(states["revenue"].sum(), 2), 0.5)
    check("Nhất quán giữa biểu đồ", "Tổng số đơn theo bang = KPI", kpi["orders"], states["orders"].sum())
    check("Nhất quán giữa biểu đồ", "Tổng số đơn theo thanh toán = KPI", kpi["orders"], pays["orders"].sum())
    unknown = pays.loc[pays["payment_type"] == "unknown", "orders"].sum()
    check("Nhất quán giữa biểu đồ", "Đơn không có dữ liệu thanh toán (đã biết: 1 đơn)", 1, unknown)
    return kpi


def rfm_checks(kpi: pd.Series) -> pd.Series:
    overview = run(Q.rfm_overview(ALL)).fillna(0).iloc[0]
    segments = run(Q.rfm_segments(ALL))
    pool = run(Q.campaign_pool(ALL))
    check("RFM, Churn, DSS", "Số khách RFM = số khách có đơn hợp lệ", kpi["customers"], overview["customers"])
    check("RFM, Churn, DSS", "Tổng khách các phân khúc = số khách RFM", overview["customers"], segments["customers"].sum())
    check("RFM, Churn, DSS", "Tổng khách trang DSS = số khách RFM", overview["customers"], pool["customers"].sum())
    cooling = pool.loc[pool["bucket"].between(91, 151), "customers"].sum()
    check("RFM, Churn, DSS", "Khách sắp rời bỏ: trang DSS = trang Churn", overview["cooling"], cooling)

    recompute = one(f"""
        with {raw_sources()},
        valid as (
            select c.customer_unique_id as u, o.order_id, o.purchased_at
            from o join (select distinct order_id from i) using (order_id) join c using (customer_id)
            where {VALID}
        ),
        ref as (select date_add(date(max(purchased_at)), interval 1 day) as d from valid),
        m as (
            select u,
                   date_diff((select d from ref), date(max(purchased_at)), day) as recency,
                   count(distinct order_id) as frequency
            from valid group by u
        )
        select count(*) as n,
               countif(r.customer_unique_id is null) as missing,
               countif(m.recency != r.recency_days) as recency_diff,
               countif(m.frequency != r.frequency_orders) as frequency_diff,
               countif((m.recency > 180) != r.is_churn) as churn_diff
        from m left join {MART}.fct_customer_rfm` r on r.customer_unique_id = m.u
    """)
    check("RFM, Churn, DSS", "Khách tính lại từ dữ liệu gốc thiếu trong fct_customer_rfm", 0, recompute["missing"])
    check("RFM, Churn, DSS", "Recency lệch so với tính lại từ dữ liệu gốc", 0, recompute["recency_diff"])
    check("RFM, Churn, DSS", "Frequency lệch so với tính lại từ dữ liệu gốc", 0, recompute["frequency_diff"])
    check("RFM, Churn, DSS", "Cờ churn (> 180 ngày) lệch", 0, recompute["churn_diff"])
    rules = one(f"""
        select countif(customer_segment != case
            when r_score >= 4 and f_score >= 4 then 'Champions'
            when r_score >= 3 and f_score >= 3 then 'Loyal Customers'
            when r_score >= 4 and f_score = 1 then 'Promising / New Customers'
            when r_score = 3 and f_score = 1 then 'Potential Loyalists'
            when r_score <= 2 and f_score >= 3 then 'At Risk / Need Attention'
            when r_score = 2 and f_score = 1 then 'About to Sleep'
            else 'Lost / Hibernating' end) as wrong
        from {MART}.fct_customer_rfm`
    """)
    check("RFM, Churn, DSS", "Khách gán sai phân khúc theo quy tắc R, F", 0, rules["wrong"])
    return overview


def ui_checks() -> list:
    from streamlit.testing.v1 import AppTest

    pages = [
        ("Tổng quan", None),
        ("Xu hướng và địa lý", "views/trends_geo.py"),
        ("Phân khúc RFM", "views/rfm.py"),
        ("Churn và giữ chân", "views/churn.py"),
        ("Chiến dịch giữ chân", "views/decision.py"),
    ]
    rows = []
    for name, path in pages:
        at = AppTest.from_file(str(APP_DIR / "Home.py"), default_timeout=180)
        at.secrets["bigquery"] = CFG
        at.run()
        if path:
            at.switch_page(path)
        started = time.perf_counter()
        at.run()
        errors = [str(e.value) for e in at.exception] + [e.value for e in at.error]
        rows.append({
            "Trang": name,
            "Kết quả": "PASS" if not errors else "FAIL",
            "Biểu đồ": len(at.get("plotly_chart")),
            "Bảng": len(at.dataframe),
            "Thời gian (ms)": round((time.perf_counter() - started) * 1000),
            "Lỗi": "; ".join(errors)[:200],
        })
    return rows


def main() -> int:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 80)
    started = time.perf_counter()
    pipeline_checks()
    kpi = dashboard_checks()
    overview = rfm_checks(kpi)
    print("\n=== KIỂM TRA SỐ LIỆU ===")
    print(pd.DataFrame(results).to_string(index=False))
    print("\n=== KIỂM TRA GIAO DIỆN ===")
    ui = pd.DataFrame(ui_checks())
    print(ui.to_string(index=False))
    print("\n=== SỐ LIỆU CHÍNH (toàn bộ dữ liệu) ===")
    print(f"Đơn hợp lệ: {int(kpi['orders']):,} · Doanh thu: R$ {kpi['revenue']:,.2f} · Khách: {int(kpi['customers']):,}")
    print(f"Tỷ lệ churn: {overview['churn_rate']:.2%} · Khách sắp rời bỏ: {int(overview['cooling']):,} · Ngày mốc: {overview['last_purchase']}")
    failed = sum(r["Kết quả"] == "FAIL" for r in results) + int((ui["Kết quả"] == "FAIL").sum())
    print(f"\nTổng: {len(results) + len(ui)} kiểm tra, {failed} lỗi · {time.perf_counter() - started:,.0f} giây · {date.today():%d/%m/%Y}")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())

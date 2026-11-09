import sys
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

from utils import queries as Q
from utils.bigquery import _job_config
from utils.campaign import Scenario, evaluate
from utils.filters import DEFAULT_RANGE, Filters

CFG = tomllib.loads((APP_DIR / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["bigquery"]
CREDS = service_account.Credentials.from_service_account_file(str((APP_DIR / CFG["key_path"]).resolve()))
CLIENT = bigquery.Client(credentials=CREDS, project=CFG["project"], location=CFG["location"])
WEEKDAYS = {1: "Chủ nhật", 2: "Thứ 2", 3: "Thứ 3", 4: "Thứ 4", 5: "Thứ 5", 6: "Thứ 6", 7: "Thứ 7"}
DEF = Filters(DEFAULT_RANGE[0], DEFAULT_RANGE[1], (), ())


def run(spec) -> pd.DataFrame:
    sql, params = spec
    job = CLIENT.query(sql, job_config=_job_config(params, True))
    return job.to_dataframe(create_bqstorage_client=False)


def head(title: str) -> None:
    print(f"\n=== {title} ===")


def show(frame: pd.DataFrame) -> None:
    print(frame.to_string(index=False))


def kpi(f: Filters, title: str) -> None:
    row = run(Q.kpi_compare(f)).fillna(0).iloc[0]
    orders, revenue = int(row["orders"]), float(row["revenue"])
    print(
        f"{title}: doanh thu {revenue:,.2f} | đơn {orders:,} | AOV {revenue / orders:,.2f} | "
        f"phí ship/đơn {row['freight'] / orders:,.2f} | khách {int(row['customers']):,}"
    )
    if row["prev_orders"]:
        p_orders, p_revenue = int(row["prev_orders"]), float(row["prev_revenue"])
        print(
            f"  kỳ trước: doanh thu {p_revenue:,.2f} ({revenue / p_revenue - 1:+.2%}) | "
            f"đơn {p_orders:,} ({orders / p_orders - 1:+.2%}) | "
            f"AOV {p_revenue / p_orders:,.2f} | phí ship/đơn {row['prev_freight'] / p_orders:,.2f} | "
            f"khách {int(row['prev_customers']):,} ({row['customers'] / row['prev_customers'] - 1:+.2%})"
        )


def overview() -> None:
    head("TỔNG QUAN (kỳ mặc định 01/01/2017 - 31/08/2018)")
    kpi(DEF, "Kỳ mặc định")
    kpi(Filters(date(2018, 1, 1), date(2018, 6, 30), (), ()), "6 tháng đầu 2018")
    monthly = run(Q.revenue_by_month(DEF))
    monthly["month"] = pd.to_datetime(monthly["month"]).dt.strftime("%m/%Y")
    show(monthly)
    cats = run(Q.sales_by_category(DEF))
    total = cats["revenue"].sum()
    cats["share_revenue"] = cats["revenue"] / total
    print(f"Số danh mục: {len(cats)}")
    show(cats.nlargest(10, "revenue"))
    show(cats.nlargest(5, "orders")[["category", "orders"]])
    pays = run(Q.payment_mix(DEF))
    pays["share"] = pays["orders"] / pays["orders"].sum()
    show(pays)
    prods = run(Q.top_products(DEF))
    print(f"Top 10 sản phẩm: doanh thu {prods['revenue'].sum():,.2f}, chiếm {prods['revenue'].sum() / total:.2%}")
    show(prods[["category", "revenue", "orders", "avg_price"]])


def trends() -> None:
    head("XU HƯỚNG VÀ ĐỊA LÝ (kỳ mặc định)")
    quarter = run(Q.sales_by_period(DEF, "quarter"))
    quarter["period"] = pd.to_datetime(quarter["period"]).dt.to_period("Q").astype(str)
    show(quarter)
    yoy = run(Q.same_months_by_year(DEF))
    pivot = yoy.pivot(index="month", columns="year", values=["revenue", "orders"])
    show(pivot.reset_index())
    for field in ("revenue", "orders"):
        p = yoy.pivot(index="month", columns="year", values=field)
        print(f"Tháng 1-8, {field}: 2017 {p[2017].sum():,.2f} | 2018 {p[2018].sum():,.2f} | {p[2018].sum() / p[2017].sum() - 1:+.2%}")
    grid = run(Q.orders_by_weekday_hour(DEF))
    total = grid["orders"].sum()
    peak = grid.nlargest(3, "orders")
    for _, r in peak.iterrows():
        print(f"Cao điểm: {WEEKDAYS[int(r['day_of_week'])]} {int(r['hour'])}h, {int(r['orders']):,} đơn")
    by_day = grid.groupby("day_of_week")["orders"].sum()
    for d, v in by_day.items():
        print(f"{WEEKDAYS[int(d)]}: {int(v):,} đơn ({v / total:.2%})")
    by_hour = grid.groupby("hour")["orders"].sum()
    print(f"Đơn từ 10h đến trước 22h: {by_hour.loc[10:21].sum() / total:.2%} | từ 0h đến 6h: {by_hour.loc[0:5].sum() / total:.2%}")
    states = run(Q.state_summary(DEF))
    states["share_revenue"] = states["revenue"] / states["revenue"].sum()
    states["share_orders"] = states["orders"] / states["orders"].sum()
    show(states.sort_values("revenue", ascending=False))
    price = states["revenue"] / (1 + states["freight_ratio"])
    print(f"Cả nước: phí ship/giá hàng {(price * states['freight_ratio']).sum() / price.sum():.2%}")
    w = states["delivered_orders"]
    print(f"Cả nước: giao trễ {(states['late_rate'] * w).sum() / w.sum():.2%} | ngày giao TB {(states['delivery_days'] * w).sum() / w.sum():.2f}")
    print(f"Cả nước: AOV {states['revenue'].sum() / states['orders'].sum():,.2f}")
    show(run(Q.top_cities(DEF)))


def rfm() -> pd.Series:
    head("PHÂN KHÚC RFM (toàn bộ lịch sử)")
    overview = run(Q.rfm_overview(DEF)).fillna(0).iloc[0]
    show(overview.to_frame().T)
    seg = run(Q.rfm_segments(DEF))
    seg["customer_share"] = seg["customers"] / seg["customers"].sum()
    seg["revenue_share"] = seg["revenue"] / seg["revenue"].sum()
    seg["value_index"] = seg["revenue_share"] / seg["customer_share"]
    show(seg.sort_values("customers", ascending=False))
    matrix = run(Q.rfm_matrix(DEF))
    total = matrix["customers"].sum()
    for f_score, n in matrix.groupby("f_score")["customers"].sum().items():
        print(f"F = {f_score}: {int(n):,} khách ({n / total:.2%})")
    return overview


def churn(overview: pd.Series) -> None:
    head("CHURN VÀ GIỮ CHÂN")
    hist = run(Q.recency_histogram(DEF))
    show(hist)
    crossing = hist.loc[hist["bucket"] == 151, "customers"].sum()
    print(f"Sẽ quá 180 ngày trong 30 ngày tới: {int(crossing):,}")
    states = run(Q.churn_by_state(DEF))
    big = states[states["customers"] >= 300].sort_values("churn_rate")
    print(f"Số bang có từ 300 khách: {len(big)}")
    show(big)
    cats = run(Q.churn_by_last_category(DEF)).sort_values("churn_rate")
    show(cats)
    cooling = run(Q.cooling_customers(DEF))
    print(f"Danh sách sắp rời bỏ: {len(cooling)} khách, chi tiêu từ {cooling['monetary'].min():,.2f} đến {cooling['monetary'].max():,.2f}")


def decision(overview: pd.Series) -> None:
    head("CHIẾN DỊCH GIỮ CHÂN (giả định mặc định)")
    pool = run(Q.campaign_pool(DEF))
    for col in ["customers", "orders", "repeaters", "monetary"]:
        pool[col] = pool[col].fillna(0).astype(float)
    organic = pool["repeaters"].sum() / pool["customers"].sum()
    cooling = pool[pool["bucket"].between(91, 151)]
    by_seg = cooling.groupby("segment")[["customers", "monetary"]].sum()
    by_seg["share"] = by_seg["customers"] / by_seg["customers"].sum()
    show(by_seg.sort_values("customers", ascending=False).reset_index())
    by_state = cooling.groupby("state")[["customers", "monetary"]].sum().nlargest(5, "customers")
    show(by_state.reset_index())
    customers = cooling["customers"].sum()
    aov = cooling["monetary"].sum() / cooling["orders"].sum()
    print(f"N = {customers:,.0f} | AOV = {aov:,.2f} | o = {organic:.2%} | m = 30%")
    scenarios = [
        Scenario("A. Email nhắc nhở", 0.6, 0.02, 0.0, 0.5),
        Scenario("B. Voucher 10%", 0.6, 0.05, 0.10, 0.5),
        Scenario("C. Voucher 20%", 0.6, 0.08, 0.20, 0.5),
    ]
    table = pd.DataFrame([evaluate(s, customers, aov, organic, 0.30) for s in scenarios])
    show(table[["scenario", "reached", "buyers", "revenue", "discount_cost", "contact_cost", "spend", "profit", "roi", "breakeven"]])


def main() -> None:
    target = APP_DIR / "report_numbers.txt"
    sys.stdout = open(target, "w", encoding="utf-8")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.float_format", lambda v: f"{v:,.4f}")
    last = run(Q.data_end()).iloc[0]["last_date"]
    print(f"Ngày cuối của dữ liệu: {last}")
    overview()
    trends()
    rfm_overview = rfm()
    churn(rfm_overview)
    decision(rfm_overview)
    sys.stdout.close()
    sys.stdout = sys.__stdout__
    print(f"Đã ghi số liệu vào {target}")


if __name__ == "__main__":
    main()

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.bigquery import load_many
from utils.charts import ACCENT, MUTED, NEUTRAL, bar, brl, change, highlight, kpi_row, line, num, pct, show
from utils.filters import sidebar_filters
from utils.layout import card, note, page_header, provenance, section, table_view
from utils.queries import kpi_compare, payment_mix, revenue_by_month, sales_by_category, top_products

PAYMENT_LABELS = {
    "credit_card": "Thẻ tín dụng",
    "boleto": "Boleto",
    "voucher": "Voucher",
    "debit_card": "Thẻ ghi nợ",
    "not_defined": "Không xác định",
    "unknown": "Không có dữ liệu",
}
TABLES = ["fct_order_items_sales", "dim_time", "dim_customers", "dim_products", "dim_payments"]


def summarize(row, prefix=""):
    orders = int(row[prefix + "orders"])
    revenue = float(row[prefix + "revenue"])
    return {
        "orders": orders,
        "revenue": revenue,
        "aov": revenue / orders if orders else 0,
        "freight": float(row[prefix + "freight"]) / orders if orders else 0,
        "customers": int(row[prefix + "customers"]),
    }

f = sidebar_filters()
results = load_many(
    {
        "kpi": kpi_compare(f),
        "monthly": revenue_by_month(f),
        "categories": sales_by_category(f),
        "payments": payment_mix(f),
        "products": top_products(f),
    },
    label="Trang Tổng quan",
)

kpi = results["kpi"].fillna(0).iloc[0]
cur = summarize(kpi)

page_header(
    "Tổng quan kinh doanh",
    "Quy mô doanh số của sàn trong kỳ đang chọn, so với kỳ liền trước cùng độ dài, "
    "và đâu là danh mục cùng sản phẩm đang kéo doanh thu.",
    f.scope(),
)

if cur["orders"] == 0:
    st.info("Không có đơn hàng nào khớp bộ lọc hiện tại. Hãy nới khoảng ngày hoặc bỏ bớt bang/danh mục.")
    st.stop()

prev_f = f.previous()
prev = summarize(kpi, "prev_") if prev_f else {}

section("Chỉ số chính")
kpi_row([
    ("Doanh thu", brl(cur["revenue"]), change(cur["revenue"], prev.get("revenue")), "normal",
     "Tổng price + freight_value của các dòng hàng, đã loại đơn canceled và unavailable."),
    ("Số đơn hàng", num(cur["orders"]), change(cur["orders"], prev.get("orders")), "normal",
     "Số order_id khác nhau trong kỳ."),
    ("Giá trị đơn TB", brl(cur["aov"], short=False), change(cur["aov"], prev.get("aov")), "normal",
     "AOV = doanh thu / số đơn, đã gồm phí vận chuyển."),
    ("Phí ship TB / đơn", brl(cur["freight"], short=False), change(cur["freight"], prev.get("freight")),
     "inverse", "Tổng freight_value / số đơn. Phí tăng là tín hiệu xấu nên mũi tên lên hiển thị màu đỏ."),
    ("Khách hàng", num(cur["customers"]), change(cur["customers"], prev.get("customers")), "normal",
     "Số customer_unique_id khác nhau đã phát sinh đơn trong kỳ."),
])
if prev_f:
    st.caption(
        f"Phần trăm thay đổi so với kỳ liền trước cùng độ dài: "
        f"{prev_f.start:%d/%m/%Y} - {prev_f.end:%d/%m/%Y}."
    )
else:
    st.caption("Không hiển thị thay đổi vì kỳ liền trước nằm ngoài phạm vi dữ liệu (trước 10/2016).")

section("Doanh thu theo thời gian")
monthly = results["monthly"].copy()
month_end = monthly["month"] + pd.DateOffset(months=1) - pd.Timedelta(days=1)
monthly["partial"] = (monthly["month"] < pd.Timestamp(f.start)) | (month_end > pd.Timestamp(f.end))
full = monthly[~monthly["partial"]]
peak = (full if not full.empty else monthly).nlargest(1, "revenue").iloc[0]

with card(
    f"Doanh thu đạt đỉnh {brl(peak['revenue'])} vào tháng {peak['month']:%m/%Y}",
    "Tổng price + freight_value theo tháng đặt hàng · đơn vị R$",
):
    fig = go.Figure(
        line(
            monthly["month"],
            monthly["revenue"],
            hollow=monthly["partial"],
            hovertemplate="Tháng %{x|%m/%Y}<br><b>R$ %{y:,.0f}</b><extra></extra>",
        )
    )
    fig.update_xaxes(tickformat="%m/%Y", dtick="M3")
    fig.update_yaxes(title="Doanh thu (R$)", rangemode="tozero")
    show(fig, 320)
    if monthly["partial"].any():
        note("Điểm rỗng là tháng chưa đủ ngày trong khoảng lọc nên không dùng để so sánh với các tháng khác.")
    table_view(
        monthly[["month", "revenue", "orders"]].assign(month=monthly["month"].dt.strftime("%m/%Y")),
        {
            "month": "Tháng",
            "revenue": st.column_config.NumberColumn("Doanh thu (R$)", format="%.0f"),
            "orders": st.column_config.NumberColumn("Số đơn", format="%d"),
        },
        "doanh_thu_theo_thang.csv",
    )

section("Danh mục và phương thức thanh toán")
choice = st.segmented_control(
    "Xếp hạng danh mục theo", ["Doanh thu", "Số đơn"], default="Doanh thu", key="ov_rank"
)
field = "orders" if choice == "Số đơn" else "revenue"
left, right = st.columns([3, 2], gap="medium")

with left:
    cats = results["categories"].nlargest(10, field).sort_values(field)
    leader = cats.iloc[-1]
    leader_value = f"{num(leader[field])} đơn" if field == "orders" else brl(leader[field])
    with card(
        f"{leader['category']} dẫn đầu với {leader_value}",
        f"10 danh mục lớn nhất theo {choice.lower()} · tên danh mục bản tiếng Anh",
    ):
        fig = go.Figure(
            bar(
                cats[field],
                cats["category"],
                highlight(cats["category"], leader["category"]),
                hovertemplate="%{y}<br><b>%{x:,.0f}</b><extra></extra>",
            )
        )
        fig.update_xaxes(title="Doanh thu (R$)" if field == "revenue" else "Số đơn")
        show(fig, 400)
        table_view(
            results["categories"].sort_values(field, ascending=False),
            {
                "category": "Danh mục",
                "revenue": st.column_config.NumberColumn("Doanh thu (R$)", format="%.0f"),
                "orders": st.column_config.NumberColumn("Số đơn", format="%d"),
            },
            "danh_muc.csv",
            label="Xem toàn bộ danh mục",
        )

with right:
    pay = results["payments"].copy()
    pay["share"] = pay["orders"] / pay["orders"].sum()
    pay["label"] = pay["payment_type"].map(PAYMENT_LABELS).fillna(pay["payment_type"])
    pay = pay.sort_values("share")
    top_pay = pay.iloc[-1]
    with card(
        f"{top_pay['label']} chiếm {pct(top_pay['share'])} số đơn",
        "Phương thức có giá trị thanh toán lớn nhất trong mỗi đơn",
    ):
        fig = go.Figure(
            bar(
                pay["share"],
                pay["label"],
                highlight(pay["label"], top_pay["label"]),
                text=[pct(s) for s in pay["share"]],
                textposition="outside",
                textfont=dict(color=MUTED, size=12),
                cliponaxis=False,
                customdata=pay["orders"],
                hovertemplate="%{y}<br><b>%{customdata:,} đơn</b><extra></extra>",
            )
        )
        fig.update_xaxes(visible=False, range=[0, 1.18])
        show(fig, 400)

section("Sản phẩm bán chạy")
prods = results["products"].copy()
prods["product"] = prods["product_id"].str[:8] + "…"
with card(
    f"Top 10 sản phẩm tạo ra {brl(prods['revenue'].sum())} doanh thu",
    f"Tương đương {pct(prods['revenue'].sum() / cur['revenue'])} doanh thu toàn kỳ, "
    f"trên tổng {num(len(results['categories']))} danh mục",
):
    st.dataframe(
        prods[["product", "category", "revenue", "orders", "avg_price"]],
        hide_index=True,
        width="stretch",
        column_config={
            "product": st.column_config.TextColumn("Mã sản phẩm", width="small"),
            "category": "Danh mục",
            "revenue": st.column_config.ProgressColumn(
                "Doanh thu (R$)", format="%.0f", min_value=0, max_value=float(prods["revenue"].max())
            ),
            "orders": st.column_config.NumberColumn("Số đơn", format="%d"),
            "avg_price": st.column_config.NumberColumn("Giá TB (R$)", format="%.2f"),
        },
    )
    st.download_button(
        "Tải CSV", prods.to_csv(index=False).encode("utf-8-sig"), "top_san_pham.csv", "text/csv"
    )
    note("Mã sản phẩm rút gọn 8 ký tự đầu; bản CSV giữ nguyên mã đầy đủ.")

provenance(TABLES)

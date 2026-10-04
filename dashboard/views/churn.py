import plotly.graph_objects as go
import streamlit as st

from utils.bigquery import load_many
from utils.charts import (
    ACCENT,
    MUTED,
    NEUTRAL,
    SERIOUS,
    bar,
    brl,
    highlight,
    kpi_row,
    legend_swatches,
    num,
    pct,
    reference_line,
    show,
)
from utils.filters import sidebar_filters
from utils.layout import card, note, page_header, provenance, section, table_view
from utils.queries import (
    churn_by_last_category,
    churn_by_state,
    cooling_customers,
    recency_histogram,
    rfm_overview,
)

CHURN_DAYS = 180
COOLING_FROM = 91
MIN_CUSTOMERS = 300
TABLES = ["fct_customer_rfm", "dim_customers", "dim_products", "fct_order_items_sales"]

f = sidebar_filters()
results = load_many(
    {
        "overview": rfm_overview(f),
        "histogram": recency_histogram(f),
        "states": churn_by_state(f),
        "categories": churn_by_last_category(f),
        "cooling": cooling_customers(f),
    },
    label="Trang Churn và giữ chân",
)
overview = results["overview"].fillna(0).iloc[0]
ref_date = overview["last_purchase"]

page_header(
    "Churn và giữ chân",
    f"Ai đang rời đi, ở đâu và vì mua gì. Một khách bị coi là churn khi đã quá "
    f"{CHURN_DAYS} ngày chưa quay lại; nhóm {COOLING_FROM}-{CHURN_DAYS} ngày là nhóm "
    "còn kịp giữ chân.",
    [("Tính đến", f"{ref_date:%d/%m/%Y}")] + f.scope(dates=False, categories=False)
    + [("Ngưỡng churn", f"{CHURN_DAYS} ngày")],
)

if int(overview["customers"]) == 0:
    st.info("Không có khách hàng nào khớp bộ lọc hiện tại.")
    st.stop()

section("Mức độ rời bỏ")
kpi_row([
    ("Tỷ lệ churn", pct(overview["churn_rate"]), None, "normal",
     f"Tỷ lệ khách có recency lớn hơn {CHURN_DAYS} ngày (cột is_churn)."),
    ("Khách còn hoạt động", num(overview["active"]), None, "normal",
     f"Khách mua lại trong vòng {CHURN_DAYS} ngày gần nhất."),
    ("Khách sắp rời bỏ", num(overview["cooling"]), None, "normal",
     f"Recency từ {COOLING_FROM} đến {CHURN_DAYS} ngày, chưa churn nhưng đã lâu không mua."),
    ("Chi tiêu của nhóm sắp rời bỏ", brl(overview["cooling_value"]), None, "normal",
     "Tổng chi tiêu lịch sử của nhóm trên, cho thấy giá trị đang có nguy cơ mất."),
])

hist = results["histogram"].copy()
hist["label"] = hist["bucket"].astype(int).astype(str) + "-" + (hist["bucket"] + 29).astype(int).astype(str)
hist["status"] = [
    "Đã churn" if b > CHURN_DAYS else ("Sắp rời bỏ" if b >= COOLING_FROM else "Còn hoạt động")
    for b in hist["bucket"]
]
STATUS_COLORS = {"Còn hoạt động": ACCENT, "Sắp rời bỏ": SERIOUS, "Đã churn": NEUTRAL}

with card(
    f"{pct(overview['churn_rate'])} khách đã quá {CHURN_DAYS} ngày chưa quay lại",
    "Số khách theo nhóm 30 ngày kể từ lần mua cuối",
):
    fig = go.Figure(
        go.Bar(
            x=hist["bucket"] + 14.5,
            y=hist["customers"],
            width=28,
            marker=dict(color=[STATUS_COLORS[s] for s in hist["status"]], cornerradius=4),
            customdata=hist[["label", "status"]],
            hovertemplate=(
                "<b>%{customdata[0]} ngày</b><br>%{y:,} khách<br>%{customdata[1]}<extra></extra>"
            ),
        )
    )
    reference_line(fig, CHURN_DAYS + 0.5, f"Ngưỡng churn {CHURN_DAYS} ngày")
    fig.update_xaxes(title="Số ngày từ lần mua cuối", dtick=60, rangemode="tozero")
    fig.update_yaxes(title="Số khách")
    show(fig, 340)
    st.markdown(
        legend_swatches([(k, v) for k, v in STATUS_COLORS.items()]), unsafe_allow_html=True
    )
    table_view(
        hist[["label", "status", "customers", "monetary"]],
        {
            "label": "Nhóm ngày",
            "status": "Trạng thái",
            "customers": st.column_config.NumberColumn("Số khách", format="%d"),
            "monetary": st.column_config.NumberColumn("Chi tiêu lịch sử (R$)", format="%.0f"),
        },
        "phan_bo_recency.csv",
    )

section("Churn tập trung ở đâu")
left, right = st.columns(2, gap="medium")

with left:
    by_state = results["states"]
    overall = (by_state["churn_rate"] * by_state["customers"]).sum() / by_state["customers"].sum()
    shown = by_state[by_state["customers"] >= MIN_CUSTOMERS].sort_values("churn_rate")
    if shown.empty:
        shown = by_state.sort_values("churn_rate")
    worst = shown.iloc[-1]
    with card(
        f"{worst['state']} có tỷ lệ churn cao nhất: {pct(worst['churn_rate'])}",
        f"Chỉ hiển thị bang có từ {MIN_CUSTOMERS} khách để tỷ lệ đủ ổn định",
    ):
        fig = go.Figure(
            bar(
                shown["churn_rate"],
                shown["state"],
                highlight(shown["state"], worst["state"]),
                customdata=shown["customers"],
                hovertemplate="%{y}<br>Churn <b>%{x:.1%}</b><br>%{customdata:,} khách<extra></extra>",
            )
        )
        reference_line(fig, overall, f"Trung bình cả nước {pct(overall)}")
        fig.update_xaxes(title="Tỷ lệ churn", tickformat=".0%", range=[0, 1])
        show(fig, 480)
        table_view(
            by_state.sort_values("churn_rate", ascending=False),
            {
                "state": "Bang",
                "customers": st.column_config.NumberColumn("Số khách", format="%d"),
                "churn_rate": st.column_config.NumberColumn("Tỷ lệ churn", format="percent"),
            },
            "churn_theo_bang.csv",
            label="Xem đủ 27 bang",
        )

with right:
    by_cat = results["categories"].sort_values("churn_rate")
    worst_cat = by_cat.iloc[-1]
    with card(
        f"Khách mua {worst_cat['category']} lần cuối rời bỏ nhiều nhất: {pct(worst_cat['churn_rate'])}",
        "15 danh mục có nhiều khách nhất, xếp theo danh mục của đơn mua gần nhất",
    ):
        fig = go.Figure(
            bar(
                by_cat["churn_rate"],
                by_cat["category"],
                highlight(by_cat["category"], worst_cat["category"]),
                customdata=by_cat["customers"],
                hovertemplate="%{y}<br>Churn <b>%{x:.1%}</b><br>%{customdata:,} khách<extra></extra>",
            )
        )
        fig.update_xaxes(title="Tỷ lệ churn", tickformat=".0%", range=[0, 1])
        fig.update_yaxes(tickfont=dict(size=11))
        show(fig, 480)
        table_view(
            by_cat.sort_values("churn_rate", ascending=False),
            {
                "category": "Danh mục",
                "customers": st.column_config.NumberColumn("Số khách", format="%d"),
                "churn_rate": st.column_config.NumberColumn("Tỷ lệ churn", format="percent"),
            },
            "churn_theo_danh_muc.csv",
        )

section("Việc cần làm ngay")
people = results["cooling"]
with card(
    f"{num(len(people))} khách cần liên hệ trước khi vượt ngưỡng churn",
    f"Khách chi tiêu cao nhất trong nhóm {COOLING_FROM}-{CHURN_DAYS} ngày chưa quay lại",
):
    st.dataframe(
        people,
        hide_index=True,
        width="stretch",
        column_config={
            "customer_unique_id": "Mã khách",
            "customer_state": st.column_config.TextColumn("Bang", width="small"),
            "segment": "Phân khúc",
            "recency_days": st.column_config.NumberColumn("Recency (ngày)", format="%d"),
            "frequency_orders": st.column_config.NumberColumn("Số đơn", format="%d"),
            "monetary": st.column_config.NumberColumn("Chi tiêu (R$)", format="%.2f"),
        },
    )
    st.download_button(
        "Tải CSV", people.to_csv(index=False).encode("utf-8-sig"),
        "khach_sap_roi_bo.csv", "text/csv"
    )
    note("Sang trang <b>Chiến dịch giữ chân</b> để ước lượng chi phí và lợi nhuận "
         "của việc tiếp cận nhóm này.")

with st.expander("Định nghĩa và lưu ý khi diễn giải"):
    st.markdown(
        f"""
- **Churn**: khách có recency lớn hơn {CHURN_DAYS} ngày (cột `is_churn` trong `fct_customer_rfm`).
- **Sắp rời bỏ**: recency từ {COOLING_FROM} đến {CHURN_DAYS} ngày.
- **Nhóm 30 ngày**: mọi trang đều dùng chung công thức `div(recency_days - 1, 30) * 30 + 1`,
  nên nhóm 91 phủ đúng 91-120 ngày và ngưỡng {CHURN_DAYS} rơi đúng ranh giới nhóm.
- **Tỷ lệ trung bình cả nước** tính trên tất cả khách trong bộ lọc, kể cả bang bị ẩn khỏi biểu đồ.
- **Lưu ý quan trọng**: khoảng 97% khách Olist chỉ mua một lần, nên churn ở đây chủ yếu phản ánh
  *thời điểm khách mua lần đầu*. Danh mục hoặc bang bán mạnh từ sớm (2017) tất yếu có churn cao hơn.
  Hãy đọc con số này là "tỷ lệ chưa quay lại", không phải "khách bỏ đi vì không hài lòng".
"""
    )

provenance(TABLES)

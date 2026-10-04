import numpy as np
import plotly.graph_objects as go
import streamlit as st

from utils.bigquery import load, load_many
from utils.charts import (
    ACCENT,
    BLUE_SCALE,
    GRID,
    INK,
    INK_2,
    MUTED,
    SEGMENT_COLORS,
    SEGMENT_ORDER,
    SEGMENT_TIER,
    SERIES,
    SURFACE,
    TIER_COLORS,
    TIER_ORDER,
    bar,
    brl,
    kpi_row,
    num,
    pct,
    show,
)
from utils.filters import sidebar_filters
from utils.layout import card, note, page_header, provenance, section, table_view
from utils.queries import rfm_matrix, rfm_overview, rfm_segments, segment_customers

ACTIONS = {
    "Champions": "Ưu đãi VIP, mời dùng thử sản phẩm mới, xin đánh giá và giới thiệu bạn bè",
    "Loyal Customers": "Tích điểm, gợi ý sản phẩm bổ trợ (cross-sell) theo danh mục đã mua",
    "Promising / New Customers": "Email chăm sóc sau mua, mã giảm giá cho đơn thứ 2 trong 30 ngày",
    "Potential Loyalists": "Nhắc lại sản phẩm đã xem, miễn phí ship cho đơn kế tiếp",
    "About to Sleep": "Ưu đãi có thời hạn ngắn để kéo quay lại trước khi mất hẳn",
    "At Risk / Need Attention": "Liên hệ cá nhân hóa, ưu đãi sâu vì đây là khách từng mua nhiều lần",
    "Lost / Hibernating": "Không chi ngân sách lớn; chỉ gửi thông báo dịp lễ lớn (Black Friday)",
}
TABLES = ["fct_customer_rfm", "dim_customers"]


def short(segment: str) -> str:
    return segment.split(" / ")[0]

f = sidebar_filters()
results = load_many(
    {"overview": rfm_overview(f), "segments": rfm_segments(f), "matrix": rfm_matrix(f)},
    label="Trang Phân khúc RFM",
)
overview = results["overview"].fillna(0).iloc[0]
ref_date = overview["last_purchase"]

page_header(
    "Phân khúc khách hàng RFM",
    "Khách hàng là ai, đáng giá bao nhiêu và nên đối xử khác nhau ra sao. "
    "RFM chấm điểm mỗi khách theo lần mua gần nhất (R), số đơn (F) và tổng chi tiêu (M).",
    [("Tính đến", f"{ref_date:%d/%m/%Y}")] + f.scope(dates=False, categories=False)
    + [("Lưu ý", "bộ lọc ngày và danh mục không áp dụng")],
)

if int(overview["customers"]) == 0:
    st.info("Không có khách hàng nào khớp bộ lọc hiện tại.")
    st.stop()

section("Quy mô tập khách hàng")
kpi_row([
    ("Khách hàng", num(overview["customers"]), None, "normal",
     "Số customer_unique_id có ít nhất một đơn hợp lệ trong toàn bộ lịch sử."),
    ("Tỷ lệ mua lại", pct(overview["repeat_rate"]), None, "normal",
     "Tỷ lệ khách có từ 2 đơn trở lên."),
    ("Recency trung vị", f"{int(overview['median_recency'])} ngày", None, "normal",
     "Một nửa số khách mua lần cuối cách đây ít hơn con số này."),
    ("Chi tiêu TB / khách", brl(overview["avg_monetary"], short=False), None, "normal",
     "Tổng price + freight_value chia cho số khách."),
])

seg = (
    results["segments"].set_index("segment").reindex(SEGMENT_ORDER)
    .dropna(subset=["customers"]).reset_index()
)
seg["customer_share"] = seg["customers"] / seg["customers"].sum()
seg["revenue_share"] = seg["revenue"] / seg["revenue"].sum()
seg["tier"] = seg["segment"].map(SEGMENT_TIER)
seg["value_index"] = seg["revenue_share"] / seg["customer_share"]

section("Phân khúc nào đáng để đầu tư")
gap = seg.loc[seg["value_index"].idxmax()]
with card(
    f"{short(gap['segment'])} chỉ chiếm {pct(gap['customer_share'])} số khách "
    f"nhưng tạo {pct(gap['revenue_share'])} doanh thu",
    "Tỷ trọng số khách so với tỷ trọng doanh thu của từng phân khúc · "
    "khoảng cách càng rộng, mỗi khách càng đáng giá",
):
    order = seg.iloc[::-1]
    fig = go.Figure()
    for _, row in order.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[row["customer_share"], row["revenue_share"]],
                y=[row["segment"]] * 2,
                mode="lines",
                line=dict(color=GRID, width=3),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    for name, column, color in (
        ("% số khách", "customer_share", SERIES[0]),
        ("% doanh thu", "revenue_share", SERIES[1]),
    ):
        fig.add_trace(
            go.Scatter(
                x=order[column],
                y=order["segment"],
                mode="markers",
                name=name,
                marker=dict(size=13, color=color, line=dict(color=SURFACE, width=2)),
                hovertemplate=f"%{{y}}<br>{name}: <b>%{{x:.1%}}</b><extra></extra>",
            )
        )
    fig.add_annotation(
        x=max(gap["customer_share"], gap["revenue_share"]),
        y=gap["segment"],
        text=f"{pct(gap['customer_share'])} khách tạo {pct(gap['revenue_share'])} doanh thu",
        showarrow=False, xanchor="left", xshift=14, font=dict(size=11, color=INK_2),
    )
    fig.update_xaxes(
        title="Tỷ trọng", tickformat=".0%", rangemode="tozero",
        showgrid=True, gridcolor=GRID, showline=False, ticks="",
    )
    fig.update_yaxes(showgrid=False, showline=False, tickfont=dict(size=12, color=INK))
    show(fig, 360)
    note(f"Chỉ ghi số cho {gap['segment']}, phân khúc có tỷ lệ doanh thu trên số khách cao nhất. "
         "Giá trị của các phân khúc còn lại nằm trong bảng hồ sơ bên dưới.")

left, right = st.columns(2, gap="medium")

with left:
    matrix = results["matrix"]
    grid = (
        matrix.pivot(index="r_score", columns="f_score", values="customers")
        .reindex(index=[5, 4, 3, 2, 1], columns=[1, 3, 4, 5]).fillna(0).astype(float)
    )
    single = grid[1].sum() / grid.values.sum()
    with card(
        f"{pct(single)} khách chỉ mua đúng một lần",
        "Số khách theo điểm R (mua gần) và điểm F (số đơn) · độ đậm theo thang log",
    ):
        fig = go.Figure(
            go.Heatmap(
                z=np.log10(grid.values + 1),
                x=[f"F = {c}" for c in grid.columns],
                y=[f"R = {r}" for r in grid.index],
                text=[[num(v) for v in row] for row in grid.values],
                texttemplate="%{text}",
                textfont=dict(size=12, color=INK),
                colorscale=BLUE_SCALE,
                showscale=False,
                xgap=2,
                ygap=2,
                hovertemplate="%{y} · %{x}<br><b>%{text} khách</b><extra></extra>",
            )
        )
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(showline=False, ticks="")
        show(fig, 360)
        note("Con số in trong từng ô là số khách thật, không phải giá trị log. "
             "Điểm F không bao giờ bằng 2 theo quy tắc chấm điểm của model.")

with right:
    with card(
        "Phân khúc càng sang trái càng mua gần đây, càng lên cao càng chi nhiều",
        "Mỗi bong bóng là một phân khúc · kích thước theo số khách · màu theo bậc giá trị",
    ):
        fig = go.Figure()
        for tier in TIER_ORDER:
            part = seg[seg["tier"] == tier]
            if part.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=part["recency"],
                    y=part["monetary"],
                    mode="markers+text",
                    name=tier,
                    text=[short(s) for s in part["segment"]],
                    textposition="top center",
                    textfont=dict(size=11, color=MUTED),
                    marker=dict(
                        size=part["customers"],
                        sizemode="area",
                        sizeref=2.0 * seg["customers"].max() / (58**2),
                        sizemin=6,
                        color=TIER_COLORS[tier],
                        line=dict(color=SURFACE, width=2),
                    ),
                    customdata=part[["segment", "customers", "frequency"]],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>%{customdata[1]:,} khách<br>"
                        "Recency TB %{x:,.0f} ngày<br>Chi tiêu TB R$ %{y:,.0f}<br>"
                        "Số đơn TB %{customdata[2]:.2f}<extra></extra>"
                    ),
                )
            )
        fig.update_xaxes(title="Recency trung bình (ngày)", rangemode="tozero")
        fig.update_yaxes(title="Chi tiêu trung bình (R$)", range=[0, seg["monetary"].max() * 1.45])
        fig.update_layout(margin=dict(t=64))
        show(fig, 360)

section("Hồ sơ và hành động")
with card(
    "Bảng hành động cho từng phân khúc",
    "Chỉ số trung bình của mỗi nhóm, kèm cách tiếp cận đề xuất",
):
    profile = seg.assign(action=seg["segment"].map(ACTIONS))[
        ["segment", "tier", "customers", "customer_share", "revenue_share",
         "recency", "frequency", "monetary", "churn_rate", "action"]
    ]
    st.dataframe(
        profile,
        hide_index=True,
        width="stretch",
        column_config={
            "segment": st.column_config.TextColumn("Phân khúc", width="medium"),
            "tier": st.column_config.TextColumn("Bậc giá trị", width="small"),
            "customers": st.column_config.NumberColumn("Số khách", format="%d"),
            "customer_share": st.column_config.NumberColumn("% khách", format="percent"),
            "revenue_share": st.column_config.NumberColumn("% doanh thu", format="percent"),
            "recency": st.column_config.NumberColumn("Recency TB (ngày)", format="%.0f"),
            "frequency": st.column_config.NumberColumn("Số đơn TB", format="%.2f"),
            "monetary": st.column_config.NumberColumn("Chi tiêu TB (R$)", format="%.2f"),
            "churn_rate": st.column_config.NumberColumn("Churn", format="percent"),
            "action": st.column_config.TextColumn("Hành động đề xuất", width="large"),
        },
    )
    st.download_button(
        "Tải CSV", profile.to_csv(index=False).encode("utf-8-sig"), "ho_so_phan_khuc.csv", "text/csv"
    )

with card("Danh sách khách theo phân khúc", "Dùng để xuất danh sách gửi cho đội marketing"):
    picked = st.selectbox("Chọn phân khúc", list(seg["segment"]), key="rfm_segment")
    people = load(*segment_customers(f, picked), label="Danh sách khách theo phân khúc")
    st.caption(f"{num(len(people))} khách chi tiêu cao nhất của nhóm {picked}.")
    st.dataframe(
        people,
        hide_index=True,
        width="stretch",
        column_config={
            "customer_unique_id": "Mã khách",
            "customer_state": st.column_config.TextColumn("Bang", width="small"),
            "customer_city": "Thành phố",
            "recency_days": st.column_config.NumberColumn("Recency (ngày)", format="%d"),
            "frequency_orders": st.column_config.NumberColumn("Số đơn", format="%d"),
            "monetary": st.column_config.NumberColumn("Chi tiêu (R$)", format="%.2f"),
            "rfm_code": st.column_config.TextColumn("Mã RFM", width="small"),
        },
    )
    st.download_button(
        "Tải CSV", people.to_csv(index=False).encode("utf-8-sig"),
        "khach_theo_phan_khuc.csv", "text/csv"
    )

with st.expander("Định nghĩa chỉ số và quy tắc phân khúc"):
    st.markdown(
        """
- **Recency**: số ngày từ lần mua cuối đến ngày mốc (ngày mua cuối cùng trong dữ liệu + 1).
- **Frequency**: số đơn khác nhau của khách, đã bỏ đơn `canceled` và `unavailable`.
- **Monetary**: tổng `price + freight_value` của khách.
- **Điểm R và M**: chia 5 nhóm đều nhau bằng `NTILE(5)`.
  **Điểm F**: 1 đơn → 1, 2 đơn → 3, 3 đơn → 4, từ 4 đơn → 5.
- **Phân khúc** (model `fct_customer_rfm`, xét lần lượt từ trên xuống, chỉ dựa vào R và F):

| Phân khúc | Điều kiện |
|---|---|
| Champions | R ≥ 4 và F ≥ 4 |
| Loyal Customers | R ≥ 3 và F ≥ 3 |
| Promising / New Customers | R ≥ 4 và F = 1 |
| Potential Loyalists | R = 3 và F = 1 |
| At Risk / Need Attention | R ≤ 2 và F ≥ 3 |
| About to Sleep | R = 2 và F = 1 |
| Lost / Hibernating | còn lại (R = 1, F = 1) |

- **Bậc giá trị** gom 7 phân khúc thành 3 bậc để dùng cho màu: Giá trị cao (Champions, Loyal),
  Đang phát triển (Promising, Potential), Rủi ro (About to Sleep, At Risk, Lost).
- Khoảng **97% khách Olist chỉ mua một lần**, nên phân khúc chủ yếu do R quyết định.
"""
    )

provenance(TABLES)

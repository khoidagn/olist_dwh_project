import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.bigquery import load, load_many
from utils.campaign import Scenario, evaluate, profit_curve
from utils.charts import (
    ACCENT,
    GRID,
    MUTED,
    NEUTRAL,
    SEGMENT_ORDER,
    SERIES,
    SURFACE,
    bar,
    brl,
    highlight,
    kpi_row,
    num,
    pct,
    reference_line,
    show,
)
from utils.filters import sidebar_filters
from utils.layout import card, note, page_header, provenance, section, table_view
from utils.queries import campaign_pool, campaign_targets, rfm_overview

COOLING = (91, 180)
TABLES = ["fct_customer_rfm", "dim_customers"]
DEFAULT_SCENARIOS = pd.DataFrame(
    {
        "name": ["A. Email nhắc nhở", "B. Voucher 10%", "C. Voucher 20%"],
        "reach": [60.0, 60.0, 60.0],
        "response": [2.0, 5.0, 8.0],
        "discount": [0.0, 10.0, 20.0],
        "contact_cost": [0.5, 0.5, 0.5],
    }
)


def md(text: str) -> str:
    return text.replace("$", "\\$")


def bucket_label(start: int) -> str:
    return f"{start} đến {start + 29} ngày"

f = sidebar_filters()
results = load_many(
    {"pool": campaign_pool(f), "overview": rfm_overview(f)},
    label="Trang Hỗ trợ quyết định",
)
pool = results["pool"].copy()
overview = results["overview"].fillna(0).iloc[0]
for col in ["customers", "orders", "repeaters", "monetary"]:
    pool[col] = pool[col].fillna(0).astype(float)

page_header(
    "Chiến dịch giữ chân khách hàng",
    "Có nên chi tiền kéo khách sắp rời bỏ quay lại hay không, nhắm vào nhóm nào, "
    "và mức ưu đãi bao nhiêu thì còn có lãi.",
    [("Tính đến", f"{overview['last_purchase']:%d/%m/%Y}")]
    + f.scope(dates=False, categories=False)
    + [("Lưu ý", "bộ lọc ngày và danh mục không áp dụng")],
)

if pool.empty:
    st.info("Không có khách hàng nào khớp bộ lọc hiện tại.")
    st.stop()

history_repeat = pool["repeaters"].sum() / pool["customers"].sum()
cooling = pool[pool["bucket"].between(*COOLING)]
crossing = pool[pool["bucket"] == COOLING[1] - 29]

section("1. Nhận diện vấn đề")
kpi_row([
    ("Khách sắp rời bỏ", num(cooling["customers"].sum()), None, "normal",
     f"Recency từ {COOLING[0]} đến {COOLING[1]} ngày."),
    ("Sẽ churn trong 30 ngày tới", num(crossing["customers"].sum()), None, "normal",
     f"Nhóm {COOLING[1] - 29} đến {COOLING[1]} ngày, sắp vượt ngưỡng churn."),
    ("Chi tiêu lịch sử của nhóm", brl(cooling["monetary"].sum()), None, "normal",
     "Giá trị đang có nguy cơ mất nếu không làm gì."),
    ("Tỷ lệ khách từng mua lại", pct(history_repeat), None, "normal",
     "Khách có từ 2 đơn trở lên trên toàn bộ lịch sử."),
])

if cooling.empty:
    st.info("Không có khách nào trong khoảng 91 đến 180 ngày với bộ lọc hiện tại.")
else:
    left, right = st.columns(2, gap="medium")

    with left:
        by_seg = (
            cooling.groupby("segment")[["customers", "monetary"]].sum()
            .reindex(SEGMENT_ORDER).dropna().reset_index()
        )
        by_seg["share"] = by_seg["customers"] / by_seg["customers"].sum()
        top = by_seg.loc[by_seg["customers"].idxmax()]
        with card(
            f"{top['segment']} chiếm {pct(top['share'])} nhóm sắp rời bỏ",
            "Số khách sắp rời bỏ theo phân khúc RFM",
        ):
            order = by_seg.iloc[::-1]
            fig = go.Figure(
                bar(
                    order["customers"],
                    order["segment"],
                    highlight(order["segment"], top["segment"]),
                    text=[pct(v) for v in order["share"]],
                    textposition="outside",
                    textfont=dict(color=MUTED, size=12),
                    cliponaxis=False,
                    customdata=order["monetary"] / order["customers"],
                    hovertemplate=(
                        "%{y}<br><b>%{x:,} khách</b><br>"
                        "Chi tiêu TB R$ %{customdata:,.0f}<extra></extra>"
                    ),
                )
            )
            fig.update_xaxes(visible=False, range=[0, by_seg["customers"].max() * 1.25])
            show(fig, 340)

    with right:
        by_state = (
            cooling.groupby("state", as_index=False)[["customers", "monetary"]].sum()
            .nlargest(10, "customers").sort_values("customers")
        )
        lead = by_state.iloc[-1]
        with card(
            f"{lead['state']} có nhiều khách sắp rời bỏ nhất: {num(lead['customers'])} khách",
            "10 bang dẫn đầu về số khách cần giữ chân",
        ):
            fig = go.Figure(
                bar(
                    by_state["customers"],
                    by_state["state"],
                    highlight(by_state["state"], lead["state"]),
                    customdata=by_state["monetary"] / by_state["customers"],
                    hovertemplate=(
                        "%{y}<br><b>%{x:,} khách</b><br>"
                        "Chi tiêu TB R$ %{customdata:,.0f}<extra></extra>"
                    ),
                )
            )
            fig.update_xaxes(title="Số khách")
            show(fig, 340)

section("2. Thiết kế phương án")
buckets = sorted(int(b) for b in pool["bucket"].unique())
default_range = (
    (COOLING[0], COOLING[1] - 29)
    if {COOLING[0], COOLING[1] - 29} <= set(buckets)
    else (buckets[0], buckets[-1])
)
c1, c2 = st.columns([3, 2], gap="medium")
with c1:
    rmin, rmax_start = st.select_slider(
        "Nhóm mục tiêu theo số ngày từ lần mua cuối",
        options=buckets,
        value=default_range,
        format_func=bucket_label,
        key="dss_recency",
    )
    rmax = rmax_start + 29
    in_range = pool[pool["bucket"].between(rmin, rmax_start)]
    seg_options = [s for s in SEGMENT_ORDER if s in set(in_range["segment"])]
    segments = st.multiselect("Phân khúc RFM", seg_options, default=seg_options, key="dss_segments")
with c2:
    margin = st.number_input(
        "Biên lợi nhuận gộp trên doanh thu (%)", 1.0, 90.0, 30.0, 1.0, key="dss_margin",
        help="Dữ liệu Olist không có giá vốn, hãy nhập theo số liệu của doanh nghiệp.",
    ) / 100
    organic = st.number_input(
        "Tỷ lệ tự quay lại khi không có chiến dịch (%)", 0.0, 50.0,
        round(history_repeat * 100, 1), 0.1, key="dss_organic",
        help="Mặc định lấy từ dữ liệu: tỷ lệ khách từng mua từ 2 đơn trở lên.",
    ) / 100
    budget = st.number_input(
        "Ngân sách tối đa (R$, 0 là không giới hạn)", 0.0, None, 0.0, 1000.0, key="dss_budget"
    )

if not segments:
    st.info("Chọn ít nhất một phân khúc để tính toán.")
    st.stop()

target = in_range[in_range["segment"].isin(segments)]
customers = target["customers"].sum()
aov = target["monetary"].sum() / target["orders"].sum() if target["orders"].sum() else 0
st.caption(
    f"Nhóm mục tiêu hiện tại: {num(customers)} khách, {rmin} đến {rmax} ngày chưa mua, "
    f"giá trị đơn trung bình {brl(aov, short=False)} đã gồm phí vận chuyển."
)

with card(
    "Các phương án cần so sánh",
    "Giá trị mặc định chỉ là ví dụ, hãy sửa trực tiếp trong bảng theo kế hoạch thực tế",
):
    edited = st.data_editor(
        DEFAULT_SCENARIOS,
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        key="dss_scenarios",
        column_config={
            "name": st.column_config.TextColumn("Phương án", width="medium"),
            "reach": st.column_config.NumberColumn(
                "Tiếp cận được (%)", min_value=0.0, max_value=100.0, format="%.1f"
            ),
            "response": st.column_config.NumberColumn(
                "Mua thêm nhờ chiến dịch (%)", min_value=0.0, max_value=100.0, format="%.1f",
                help="Tỷ lệ khách được tiếp cận mua thêm, ngoài số khách tự quay lại.",
            ),
            "discount": st.column_config.NumberColumn(
                "Giảm giá (%)", min_value=0.0, max_value=90.0, format="%.1f"
            ),
            "contact_cost": st.column_config.NumberColumn(
                "Chi phí liên hệ / khách (R$)", min_value=0.0, format="%.2f"
            ),
        },
    )

scenarios = [
    Scenario(str(r["name"]), r["reach"] / 100, r["response"] / 100, r["discount"] / 100, r["contact_cost"])
    for r in edited.fillna(0).to_dict("records")
]

section("3. Lựa chọn phương án")
table = pd.DataFrame([evaluate(s, customers, aov, organic, margin) for s in scenarios])
table["breakeven"] = pd.to_numeric(table["breakeven"], errors="coerce")
best_idx = table["profit"].idxmax()
best, chosen = table.loc[best_idx], scenarios[best_idx]

if best["profit"] > 0:
    distance = (chosen.response - best["breakeven"]) * 100
    with card(
        md(f"Nên chọn {best['scenario']}"),
        "Phương án cho lợi nhuận tăng thêm cao nhất với giả định hiện tại",
    ):
        kpi_row([
            ("Lợi nhuận tăng thêm", brl(best["profit"]), None, "normal",
             "Lợi nhuận gộp từ đơn mua thêm, trừ chi phí giảm giá và chi phí liên hệ."),
            ("Chi phí chiến dịch", brl(best["spend"]), None, "normal",
             "Chi phí liên hệ toàn bộ nhóm cộng giá trị giảm giá đã phát ra."),
            ("Tỷ lệ mua thêm cần để hòa vốn", pct(best["breakeven"]), None, "normal",
             "Dưới mức này phương án bắt đầu lỗ."),
            ("Giả định đang dùng", pct(chosen.response), None, "normal",
             "Tỷ lệ mua thêm bạn nhập cho phương án này."),
        ])
        note(
            f"Giả định hiện tại cao hơn ngưỡng hòa vốn {f'{distance:.1f}'.replace('.', ',')} "
            f"điểm phần trăm. Nếu tỷ lệ mua thêm thực tế xuống dưới {pct(best['breakeven'])}, "
            "phương án này lỗ."
        )
        if budget > 0 and best["spend"] > budget:
            affordable = customers * budget / best["spend"]
            note(md(
                f"Ngân sách {brl(budget)} thấp hơn chi phí cần {brl(best['spend'])}, "
                f"chỉ đủ cho khoảng {num(affordable)} khách. Hãy ưu tiên khách chi tiêu cao nhất "
                "trong danh sách bên dưới."
            ))
else:
    st.warning(
        "Không phương án nào có lãi với giả định hiện tại. "
        "Hãy thu hẹp nhóm mục tiêu, giảm mức ưu đãi hoặc hạ chi phí liên hệ."
    )

shown = pd.DataFrame(
    {
        "Phương án": table["scenario"],
        "Khách tiếp cận": table["reached"].map(num),
        "Khách mua thêm": table["buyers"].map(num),
        "Doanh thu tăng thêm": table["revenue"].map(brl),
        "Chi phí": table["spend"].map(brl),
        "Lợi nhuận tăng thêm": table["profit"].map(brl),
        "ROI": table["roi"].map(lambda v: "không tính được" if pd.isna(v) else pct(v)),
        "Mua thêm để hòa vốn": table["breakeven"].map(
            lambda v: "không đạt được" if pd.isna(v) else pct(v)
        ),
    }
)

headline = "Lợi nhuận tăng thêm theo tỷ lệ khách mua thêm"
if not pd.isna(best["breakeven"]):
    headline = f"{best['scenario']} bắt đầu có lãi khi tỷ lệ mua thêm vượt {pct(best['breakeven'])}"

with card(
    md(headline),
    "Đường cong cho thấy phương án nào chịu được rủi ro tốt hơn khi khách phản hồi kém",
):
    rates = [s.response for s in scenarios] + table["breakeven"].dropna().tolist()
    responses = np.linspace(0, min(max(rates + [0.01]) * 1.6, 1.0), 60)
    palette = [SERIES[0], SERIES[1], SERIES[2]]
    fig = go.Figure()
    for i, s in enumerate(scenarios):
        color = palette[i % len(palette)]
        width = 2.5 if i == best_idx else 2
        fig.add_trace(
            go.Scatter(
                x=responses,
                y=profit_curve(s, customers, aov, organic, margin, responses),
                mode="lines",
                name=s.name,
                line=dict(color=color, width=width),
                hovertemplate=f"{s.name}<br>Mua thêm %{{x:.1%}}<br><b>R$ %{{y:,.0f}}</b><extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[s.response],
                y=[evaluate(s, customers, aov, organic, margin)["profit"]],
                mode="markers",
                marker=dict(color=color, size=11, line=dict(color=SURFACE, width=2)),
                showlegend=False,
                hovertemplate=f"{s.name}, giả định hiện tại<br><b>R$ %{{y:,.0f}}</b><extra></extra>",
            )
        )
    reference_line(fig, 0, "Hòa vốn", vertical=False)
    fig.update_xaxes(title="Tỷ lệ khách được tiếp cận mua thêm", tickformat=".0%")
    fig.update_yaxes(title="Lợi nhuận tăng thêm (R$)")
    show(fig, 400)
    note("Chấm tròn là giả định hiện tại của từng phương án. "
         "Chỗ đường cắt mức 0 chính là điểm hòa vốn.")
    table_view(shown, filename="so_sanh_phuong_an.csv", label="So sánh đầy đủ ba phương án",
               expanded=True)

section("4. Triển khai")
with card(
    "Danh sách khách mục tiêu",
    f"Khách chi tiêu cao nhất trong nhóm {rmin} đến {rmax} ngày thuộc các phân khúc đã chọn",
):
    people = load(*campaign_targets(f, rmin, rmax, tuple(segments)), label="Danh sách khách mục tiêu")
    st.caption(f"{num(len(people))} khách, sắp theo chi tiêu giảm dần.")
    st.dataframe(
        people,
        hide_index=True,
        width="stretch",
        column_config={
            "customer_unique_id": "Mã khách",
            "customer_state": st.column_config.TextColumn("Bang", width="small"),
            "customer_city": "Thành phố",
            "segment": "Phân khúc",
            "recency_days": st.column_config.NumberColumn("Recency (ngày)", format="%d"),
            "frequency_orders": st.column_config.NumberColumn("Số đơn", format="%d"),
            "monetary": st.column_config.NumberColumn("Chi tiêu (R$)", format="%.2f"),
        },
    )
    st.download_button(
        "Tải CSV", people.to_csv(index=False).encode("utf-8-sig"), "khach_muc_tieu.csv", "text/csv"
    )

with st.expander("Mô hình tính và giới hạn"):
    st.dataframe(
        pd.DataFrame(
            {
                "Ký hiệu": ["N", "AOV", "o", "m", "a", "r", "d", "c"],
                "Ý nghĩa": [
                    "Số khách mục tiêu",
                    "Giá trị đơn trung bình của nhóm mục tiêu",
                    "Tỷ lệ tự quay lại khi không có chiến dịch",
                    "Biên lợi nhuận gộp trên doanh thu",
                    "Tỷ lệ tiếp cận được",
                    "Tỷ lệ mua thêm nhờ chiến dịch",
                    "Mức giảm giá",
                    "Chi phí liên hệ mỗi khách",
                ],
                "Nguồn": ["Dữ liệu", "Dữ liệu", "Dữ liệu, có thể chỉnh"] + ["Giả định"] * 5,
            }
        ),
        hide_index=True,
        width="stretch",
    )
    st.markdown("**Khách mua thêm và doanh thu tăng thêm**")
    st.latex(r"B = N \times a \times r \qquad \Delta R = B \times \mathrm{AOV} \times (1 - d)")
    st.markdown(
        "**Chi phí chiến dịch.** Khách tự quay lại cũng dùng voucher nên vẫn tính vào chi phí giảm giá."
    )
    st.latex(r"C = N \times c + (B + N \times a \times o) \times \mathrm{AOV} \times d")
    st.markdown("**Lợi nhuận tăng thêm và ROI**")
    st.latex(r"\Pi = B \times \mathrm{AOV} \times m - C \qquad \mathrm{ROI} = \frac{\Pi}{C}")
    st.markdown("**Tỷ lệ mua thêm để hòa vốn.** Không tồn tại khi mức giảm giá lớn hơn biên lợi nhuận.")
    st.latex(r"r^{*} = \frac{a \times o \times \mathrm{AOV} \times d + c}{a \times \mathrm{AOV} \times (m - d)}")
    st.markdown(
        """
**Giới hạn của mô hình**
1. Biên lợi nhuận, tỷ lệ tiếp cận, tỷ lệ mua thêm và chi phí liên hệ là giả định do người dùng
   nhập vào, dữ liệu Olist không có các thông tin này.
2. Tỷ lệ tự quay lại mặc định lấy theo tỷ lệ khách từng mua từ 2 đơn trên toàn bộ lịch sử,
   chưa quy đổi về khung thời gian của chiến dịch.
3. Mỗi khách mua thêm được tính đúng một đơn có giá trị bằng AOV của nhóm.
"""
    )

provenance(TABLES)

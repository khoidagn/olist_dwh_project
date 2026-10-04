import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.bigquery import load_many
from utils.charts import (
    ACCENT,
    BLUE_SCALE,
    GRID,
    MUTED,
    NEUTRAL,
    SERIES,
    SURFACE,
    bar,
    brl,
    days,
    highlight,
    line,
    num,
    pct,
    reference_line,
    show,
)
from utils.filters import sidebar_filters
from utils.layout import card, note, page_header, provenance, section, table_view
from utils.queries import (
    orders_by_weekday_hour,
    same_months_by_year,
    sales_by_period,
    state_summary,
    top_cities,
)

WEEKDAYS = {2: "Thứ 2", 3: "Thứ 3", 4: "Thứ 4", 5: "Thứ 5", 6: "Thứ 6", 7: "Thứ 7", 1: "Chủ nhật"}

STATE_METRICS = {
    "Doanh thu": ("revenue", brl, "R$", False),
    "Số đơn": ("orders", num, "đơn", False),
    "Giá trị đơn TB (AOV)": ("aov", lambda v: brl(v, short=False), "R$", False),
    "Tỷ lệ phí ship / giá hàng": ("freight_ratio", pct, "%", True),
    "Tỷ lệ giao trễ": ("late_rate", pct, "%", True),
    "Số ngày giao TB": ("delivery_days", days, "ngày", True),
}
TABLES = ["fct_order_items_sales", "dim_time", "dim_customers", "dim_products"]

f = sidebar_filters()
results = load_many(
    {
        "month": sales_by_period(f, "month"),
        "quarter": sales_by_period(f, "quarter"),
        "yoy": same_months_by_year(f),
        "weekday_hour": orders_by_weekday_hour(f),
        "states": state_summary(f),
        "cities": top_cities(f),
    },
    label="Trang Xu hướng và địa lý",
)

page_header(
    "Xu hướng và địa lý",
    "Doanh số chảy theo thời gian như thế nào và tập trung ở đâu trên bản đồ Brazil, "
    "dùng để chọn thời điểm chạy khuyến mãi và ưu tiên vùng đầu tư kho vận.",
    f.scope(),
)

if results["month"].empty:
    st.info("Không có đơn hàng nào khớp bộ lọc hiện tại.")
    st.stop()

section("Theo thời gian")
c1, c2, _ = st.columns([2, 2, 4], gap="medium")
measure = c1.segmented_control("Thước đo", ["Doanh thu", "Số đơn"], default="Doanh thu", key="tg_measure")
grain_label = c2.segmented_control("Chu kỳ", ["Tháng", "Quý"], default="Tháng", key="tg_grain")
field = "orders" if measure == "Số đơn" else "revenue"
grain = "quarter" if grain_label == "Quý" else "month"
fmt = num if field == "orders" else brl
unit = "đơn" if field == "orders" else "R$"

trend = results[grain].copy()
months = 3 if grain == "quarter" else 1
period_end = trend["period"] + pd.DateOffset(months=months) - pd.Timedelta(days=1)
trend["partial"] = (trend["period"] < pd.Timestamp(f.start)) | (period_end > pd.Timestamp(f.end))
full = trend[~trend["partial"]]
best = (full if not full.empty else trend).nlargest(1, field).iloc[0]
when = f"Q{best['period'].quarter}/{best['period'].year}" if grain == "quarter" else f"{best['period']:%m/%Y}"

with card(
    f"{measure} cao nhất rơi vào {when} với {fmt(best[field])}",
    f"{measure} theo {grain_label.lower()} đặt hàng · đơn vị {unit}",
):
    fig = go.Figure(
        line(
            trend["period"],
            trend[field],
            hollow=trend["partial"],
            hovertemplate="%{x|%m/%Y}<br><b>%{y:,.0f}</b><extra></extra>",
        )
    )
    fig.update_xaxes(tickformat="%m/%Y", dtick="M3" if grain == "month" else "M6")
    fig.update_yaxes(title=f"{measure} ({unit})", rangemode="tozero")
    show(fig, 330)
    if trend["partial"].any():
        note("Điểm rỗng là kỳ chưa đủ ngày trong khoảng lọc, không dùng để so sánh.")
    table_view(
        trend[["period", "revenue", "orders"]].assign(period=trend["period"].dt.strftime("%m/%Y")),
        {
            "period": "Kỳ",
            "revenue": st.column_config.NumberColumn("Doanh thu (R$)", format="%.0f"),
            "orders": st.column_config.NumberColumn("Số đơn", format="%d"),
        },
        f"xu_huong_{grain}.csv",
    )

left, right = st.columns(2, gap="medium")

with left:
    yoy = results["yoy"]
    pivot = yoy.pivot(index="month", columns="year", values=field)
    if {2017, 2018}.issubset(pivot.columns):
        growth = pivot[2018].sum() / pivot[2017].sum() - 1
        headline = f"Tháng 1-8/2018 tăng {pct(growth)} so với cùng kỳ 2017"
    else:
        headline = "So sánh cùng kỳ tháng 1-8"
    with card(headline, f"{measure} tám tháng đầu năm, hai năm chồng lên nhau"):
        fig = go.Figure()
        for year, color in ((2017, NEUTRAL), (2018, SERIES[0])):
            if year not in pivot.columns:
                continue
            fig.add_trace(
                go.Scatter(
                    x=pivot.index,
                    y=pivot[year],
                    name=str(year),
                    mode="lines+markers+text",
                    line=dict(color=color, width=2),
                    marker=dict(size=8, color=color, line=dict(color=SURFACE, width=2)),
                    text=[str(year) if m == pivot.index.max() else "" for m in pivot.index],
                    textposition="middle right",
                    textfont=dict(color=MUTED, size=12),
                    hovertemplate=f"{year} · tháng %{{x}}<br><b>%{{y:,.0f}}</b><extra></extra>",
                )
            )
        fig.update_xaxes(title="Tháng", tickmode="linear", dtick=1, range=[0.5, 9.2])
        fig.update_yaxes(title=f"{measure} ({unit})", rangemode="tozero")
        show(fig, 330)
        note("Biểu đồ này luôn lấy tháng 1-8 của cả hai năm nên không chịu bộ lọc ngày; "
             "bộ lọc bang và danh mục vẫn áp dụng.")

with right:
    grid = results["weekday_hour"]
    heat = (
        grid.pivot(index="day_of_week", columns="hour", values="orders")
        .reindex(index=list(WEEKDAYS), columns=range(24))
        .fillna(0)
        .astype(float)
    )
    peak = grid.nlargest(1, "orders").iloc[0]
    busiest = heat.sum(axis=1).idxmax()
    with card(
        f"Giờ cao điểm là {int(peak['hour'])}h {WEEKDAYS[int(peak['day_of_week'])].lower()}",
        "Số đơn theo thứ trong tuần và giờ đặt hàng · đậm hơn là nhiều đơn hơn",
    ):
        fig = go.Figure(
            go.Heatmap(
                z=heat.values,
                x=[f"{h}h" for h in heat.columns],
                y=[WEEKDAYS[d] for d in heat.index],
                colorscale=BLUE_SCALE,
                xgap=2,
                ygap=2,
                colorbar=dict(
                    title=dict(text="Số đơn", font=dict(size=11, color=MUTED)),
                    thickness=8, len=0.85, outlinewidth=0, tickfont=dict(size=11, color=MUTED),
                ),
                hovertemplate="%{y} · %{x}<br><b>%{z:,.0f} đơn</b><extra></extra>",
            )
        )
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(dtick=3, showline=False, ticks="")
        show(fig, 330)
        note(f"{WEEKDAYS[busiest]} là ngày nhiều đơn nhất trong tuần.")

section("Theo địa lý")
metric_label = st.selectbox("Thước đo theo bang", list(STATE_METRICS), key="geo_metric")
col, formatter, axis_unit, higher_is_worse = STATE_METRICS[metric_label]

states = results["states"].copy()
data = states.dropna(subset=[col])
if data.empty:
    st.info("Không đủ dữ liệu để tính thước đo này với bộ lọc hiện tại.")
    st.stop()

ranked = data.sort_values(col)
leader = ranked.iloc[-1]
if col in ("revenue", "orders"):
    share = leader[col] / ranked[col].sum()
    headline = f"{leader['state']} dẫn đầu: {formatter(leader[col])}, bằng {pct(share)} cả nước"
else:
    headline = f"{leader['state']} cao nhất: {formatter(leader[col])}"

with card(headline, f"{metric_label} theo bang của khách hàng · {len(ranked)} bang, cột đậm là bang cao nhất"):
    fig = go.Figure(
        bar(
            ranked[col],
            ranked["state"],
            highlight(ranked["state"], leader["state"]),
            customdata=ranked[["state", "orders"]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>%{x:,.3~f}<br>%{customdata[1]:,} đơn<extra></extra>"
            ),
        )
    )
    overall = None
    if col == "freight_ratio":
        price = ranked["revenue"] / (1 + ranked["freight_ratio"])
        overall = (price * ranked["freight_ratio"]).sum() / price.sum()
    elif higher_is_worse:
        weights = ranked["delivered_orders"]
        overall = (ranked[col] * weights).sum() / weights.sum() if weights.sum() else None
    if overall is not None and pd.notna(overall):
        reference_line(fig, overall, f"Cả nước {formatter(overall)}")
    fig.update_xaxes(tickformat=".0%" if col in ("freight_ratio", "late_rate") else None)
    fig.update_yaxes(tickfont=dict(size=11))
    show(fig, 460)
    if higher_is_worse:
        note("Bang ít đơn dễ dao động mạnh, nên đọc kèm cột số đơn trong bảng bên dưới.")

with card(
    "Chi tiết theo bang",
    "Toàn bộ thước đo của 27 bang, sắp theo doanh thu giảm dần",
):
    detail = states.sort_values("revenue", ascending=False)[
        ["state", "orders", "revenue", "aov",
         "freight_ratio", "delivered_orders", "late_rate", "delivery_days"]
    ]
    st.dataframe(
        detail,
        hide_index=True,
        width="stretch",
        column_config={
            "state": st.column_config.TextColumn("Bang", width="small"),
            "orders": st.column_config.NumberColumn("Số đơn", format="%d"),
            "revenue": st.column_config.NumberColumn("Doanh thu (R$)", format="%.0f"),
            "aov": st.column_config.NumberColumn("AOV (R$)", format="%.2f"),
            "freight_ratio": st.column_config.NumberColumn("Phí ship / giá hàng", format="percent"),
            "delivered_orders": st.column_config.NumberColumn("Đơn đã giao", format="%d"),
            "late_rate": st.column_config.NumberColumn("Tỷ lệ giao trễ", format="percent"),
            "delivery_days": st.column_config.NumberColumn("Ngày giao TB", format="%.1f"),
        },
    )
    st.download_button(
        "Tải CSV", detail.to_csv(index=False).encode("utf-8-sig"), "theo_bang.csv", "text/csv"
    )

cities = results["cities"].sort_values("orders")
cities["label"] = cities["city"].str.title() + " · " + cities["state"]
top_city = cities.iloc[-1]
with card(
    f"{top_city['label']} là thành phố nhiều đơn nhất: {num(top_city['orders'])} đơn",
    "10 thành phố nhiều đơn nhất, tính ở mức đơn hàng nên đơn nhiều món không bị đếm lặp",
):
    fig = go.Figure(
        bar(
            cities["orders"],
            cities["label"],
            highlight(cities["label"], top_city["label"]),
            customdata=cities["revenue"],
            hovertemplate="%{y}<br><b>%{x:,} đơn</b><br>R$ %{customdata:,.0f}<extra></extra>",
        )
    )
    fig.update_xaxes(title="Số đơn")
    show(fig, 360)
    table_view(
        cities.sort_values("orders", ascending=False)[["city", "state", "orders", "revenue"]],
        {
            "city": "Thành phố",
            "state": "Bang",
            "orders": st.column_config.NumberColumn("Số đơn", format="%d"),
            "revenue": st.column_config.NumberColumn("Doanh thu (R$)", format="%.0f"),
        },
        "top_thanh_pho.csv",
    )

with st.expander("Định nghĩa chỉ số"):
    st.markdown(
        """
- **Tỷ lệ phí ship / giá hàng**: tổng `freight_value` chia tổng `price`.
- **Tỷ lệ giao trễ**: số đơn `delivered` có ngày giao thực tế sau ngày hẹn tính theo ngày,
  chia cho số đơn đã giao.
- **Số ngày giao TB**: trung bình số ngày từ lúc đặt đến lúc khách nhận, chỉ tính đơn đã giao.
- **Bang**: bang của khách hàng, lấy từ địa chỉ của đơn gần nhất trong `dim_customers`.
- Mọi chỉ số theo bang và thành phố được gộp ở **mức đơn hàng trước**, rồi mới cộng lên,
  để đơn nhiều món không bị đếm nhiều lần.
"""
    )

provenance(TABLES)

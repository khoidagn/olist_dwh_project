import time

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Olist Commerce Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.layout import inject_theme, sidebar_brand

inject_theme()
sidebar_brand()

pages = {
    "Kinh doanh": [
        st.Page("views/overview.py", title="Tổng quan", icon=":material/dashboard:", default=True),
        st.Page("views/trends_geo.py", title="Xu hướng và địa lý", icon=":material/public:"),
    ],
    "Khách hàng": [
        st.Page("views/rfm.py", title="Phân khúc RFM", icon=":material/groups:"),
        st.Page("views/churn.py", title="Churn và giữ chân", icon=":material/trending_down:"),
    ],
    "Ra quyết định": [
        st.Page("views/decision.py", title="Chiến dịch giữ chân", icon=":material/balance:"),
    ],
}

page = st.navigation(pages)
st.session_state["perf_log"] = []
started = time.perf_counter()
page.run()
page_ms = (time.perf_counter() - started) * 1000

with st.sidebar:
    st.divider()
    with st.expander("Hiệu năng và cache"):
        st.caption(f"Trang vừa dựng xong trong {page_ms:,.0f} ms.")
        st.toggle("Hiện bảng thông số", key="perf_show")
        st.toggle("Chạy truy vấn song song", value=True, key="perf_parallel")
        st.toggle("Dùng cache của BigQuery", value=True, key="perf_bq_cache")
        if st.button("Xóa cache Streamlit", width="stretch"):
            st.cache_data.clear()
            st.rerun()

if st.session_state.get("perf_show"):
    log = pd.DataFrame(st.session_state["perf_log"])
    with st.expander(f"Thông số hiệu năng · trang tải trong {page_ms:,.0f} ms", expanded=True):
        if log.empty:
            st.write("Trang này chưa gọi truy vấn nào.")
        else:
            st.dataframe(
                log,
                hide_index=True,
                column_config={
                    "label": "Nhóm truy vấn",
                    "queries": st.column_config.NumberColumn("Số truy vấn", format="%d"),
                    "ms": st.column_config.NumberColumn("Thời gian (ms)", format="%.0f"),
                    "source": "Nguồn dữ liệu",
                    "mb": st.column_config.NumberColumn("Dữ liệu quét (MB)", format="%.1f"),
                },
            )
            st.caption(
                f"Tổng {int(log['queries'].sum())} truy vấn · {log['ms'].sum():,.0f} ms chờ dữ liệu · "
                f"{log['mb'].sum():,.1f} MB quét trên BigQuery"
            )

from dataclasses import dataclass, replace
from datetime import date, timedelta

import streamlit as st

from utils.bigquery import load, table

MIN_DATE = date(2016, 9, 1)
MAX_DATE = date(2018, 10, 31)
DEFAULT_RANGE = (date(2017, 1, 1), date(2018, 8, 31))
DATA_START = date(2016, 10, 1)
KEYS = ("f_range", "f_states", "f_categories")

PRESETS = {
    "Toàn bộ dữ liệu": (DATA_START, MAX_DATE),
    "Năm 2018": (date(2018, 1, 1), date(2018, 8, 31)),
    "Năm 2017": (date(2017, 1, 1), date(2017, 12, 31)),
    "12 tháng gần nhất": (date(2017, 9, 1), date(2018, 8, 31)),
}


@dataclass(frozen=True)
class Filters:
    start: date
    end: date
    states: tuple
    categories: tuple

    def params(self) -> tuple:
        return (
            ("start", "DATE", self.start),
            ("end", "DATE", self.end),
            ("states", "STRING", self.states),
            ("categories", "STRING", self.categories),
        )

    def describe(self) -> str:
        states = ", ".join(self.states) if self.states else "tất cả"
        cats = f"{len(self.categories)} danh mục" if self.categories else "tất cả"
        return (
            f"{self.start:%d/%m/%Y} - {self.end:%d/%m/%Y} · "
            f"Bang: {states} · Danh mục: {cats}"
        )

    def scope(self, dates: bool = True, categories: bool = True) -> list:
        chips = []
        if dates:
            chips.append(("Kỳ", f"{self.start:%d/%m/%Y} - {self.end:%d/%m/%Y}"))
        states = ", ".join(self.states) if self.states else "27 bang"
        chips.append(("Bang", states))
        if categories:
            cats = f"{len(self.categories)} danh mục" if self.categories else "mọi danh mục"
            chips.append(("Danh mục", cats))
        return chips

    def previous(self):
        days = (self.end - self.start).days + 1
        prev_end = self.start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=days - 1)
        if prev_start < DATA_START:
            return None
        return replace(self, start=prev_start, end=prev_end)


def filter_options():
    return (
        f"""
        select 'state' as kind, customer_state as value
        from {table('dim_customers')}
        group by value
        union all
        select 'category' as kind, product_category_name_english as value
        from {table('dim_products')}
        group by value
        order by kind, value
        """,
        (),
    )


def _options():
    options = load(*filter_options(), label="Danh sách bộ lọc")
    states = options.loc[options["kind"] == "state", "value"].tolist()
    cats = options.loc[options["kind"] == "category", "value"].tolist()
    return states, cats


def _apply_preset() -> None:
    picked = st.session_state.get("f_preset")
    if picked in PRESETS:
        st.session_state["f_range"] = PRESETS[picked]


def sidebar_filters() -> Filters:
    states, cats = _options()
    ss = st.session_state
    ss.setdefault("f_range", DEFAULT_RANGE)
    ss.setdefault("f_states", [])
    ss.setdefault("f_categories", [])

    if ss.pop("_clear_preset", False):
        ss["f_preset"] = None

    with st.sidebar:
        st.caption("BỘ LỌC")
        st.selectbox(
            "Kỳ dựng sẵn",
            ["Tùy chọn"] + list(PRESETS),
            key="f_preset",
            on_change=_apply_preset,
            label_visibility="collapsed",
            placeholder="Chọn kỳ dựng sẵn",
            index=None,
        )
        with st.form("filters", border=False):
            picked_range = st.date_input(
                "Khoảng ngày đặt hàng",
                value=ss.f_range,
                min_value=MIN_DATE,
                max_value=MAX_DATE,
                format="DD/MM/YYYY",
            )
            picked_states = st.multiselect(
                "Bang khách hàng", states, default=ss.f_states, placeholder="Tất cả 27 bang"
            )
            picked_cats = st.multiselect(
                "Danh mục sản phẩm", cats, default=ss.f_categories, placeholder="Tất cả danh mục"
            )
            applied = st.form_submit_button("Áp dụng", type="primary", width="stretch")

        if applied:
            if len(picked_range) == 2:
                ss.f_range = tuple(picked_range)
            ss.f_states = picked_states
            ss.f_categories = picked_cats
            if PRESETS.get(ss.get("f_preset")) != ss.f_range:
                ss["_clear_preset"] = True
            st.rerun()

        if st.button("Đặt lại", width="stretch"):
            for key in KEYS:
                ss.pop(key, None)
            ss["_clear_preset"] = True
            st.rerun()

    start, end = ss.f_range
    return Filters(start, end, tuple(ss.f_states), tuple(ss.f_categories))

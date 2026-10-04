from contextlib import contextmanager
from datetime import datetime

import pandas as pd
import streamlit as st

from utils.bigquery import CACHE_TTL, dataset_ref, load
from utils.queries import data_end
from utils.theme import CSS

APP_NAME = "Olist Commerce Intelligence"
APP_SUB = "Kho dữ liệu bán hàng · Nhóm 5 · CO4031"


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def inject_theme() -> None:
    if not st.session_state.get("_theme_done"):
        st.session_state["_theme_done"] = True
    _html(CSS)


def sidebar_brand() -> None:
    with st.sidebar:
        _html(f'<div class="sb-brand">{APP_NAME}</div><div class="sb-sub">{APP_SUB}</div>')


def page_header(title: str, lead: str, scope: list) -> None:
    _html(f'<div class="page-head"><h1>{title}</h1><p class="page-lead">{lead}</p></div>')
    chips = "".join(f'<span class="v"><b>{k}</b> {v}</span>' for k, v in scope)
    _html(f'<div class="scope"><span class="k">Phạm vi</span>{chips}</div>')


def section(label: str) -> None:
    _html(f'<div class="eyebrow">{label}</div>')


@contextmanager
def card(headline: str, subtitle: str | None = None):
    with st.container(border=True):
        sub = f'<div class="s">{subtitle}</div>' if subtitle else ""
        _html(f'<div class="card-head"><div class="h">{headline}</div>{sub}</div>')
        yield


def note(text: str) -> None:
    _html(f'<div class="card-note">{text}</div>')


def table_view(
    frame: pd.DataFrame,
    column_config: dict | None = None,
    filename: str | None = None,
    label: str = "Xem số liệu dạng bảng",
    expanded: bool = False,
) -> None:
    with st.expander(label, expanded=expanded):
        st.dataframe(frame, hide_index=True, column_config=column_config or {})
        if filename:
            st.download_button(
                "Tải CSV",
                frame.to_csv(index=False).encode("utf-8-sig"),
                filename,
                "text/csv",
                key=f"dl_{filename}",
            )


def provenance(tables: list, extra: str | None = None) -> None:
    used = " · ".join(f"<code>{t}</code>" for t in tables)
    last_date = load(*data_end(), label="Ngày cuối của dữ liệu").iloc[0]["last_date"]
    asof_text = f"{last_date:%d/%m/%Y}" if pd.notna(last_date) else "chưa rõ"
    lines = [
        f"<b>Bảng dùng trên trang này</b> {used}.",
        f"<b>Dữ liệu đến</b> {asof_text} · <b>Cache</b> {CACHE_TTL} · "
        f"<b>Tải lúc</b> {datetime.now():%H:%M %d/%m/%Y}.",
    ]
    if extra:
        lines.append(extra)
    _html('<div class="provenance">' + "<br>".join(lines) + "</div>")

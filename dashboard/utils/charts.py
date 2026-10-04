import plotly.graph_objects as go
import streamlit as st

from utils.theme import (
    ACCENT,
    ACCENT_DEEP,
    AXIS,
    BLUE_SCALE,
    CRITICAL,
    GOOD,
    GRID,
    INK,
    INK_2,
    MUTED,
    NEUTRAL,
    PLOTLY_CONFIG,
    SEGMENT_COLORS,
    SEGMENT_ORDER,
    SEGMENT_TIER,
    SERIES,
    SERIOUS,
    SURFACE,
    TIER_COLORS,
    TIER_ORDER,
    WARNING,
)

TEXT = INK_2
BAR_RADIUS = 4
BAR_GAP = 0.34


def _vn(text: str) -> str:
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def num(value: float) -> str:
    return _vn(f"{value:,.0f}")


def pct(value: float, digits: int = 1) -> str:
    return _vn(f"{value * 100:.{digits}f}") + "%"


def brl(value: float, short: bool = True) -> str:
    if short and abs(value) >= 1e6:
        return f"R$ {_vn(f'{value / 1e6:.1f}')} tr"
    if short and abs(value) >= 1e3:
        return f"R$ {_vn(f'{value / 1e3:.1f}')} k"
    return f"R$ {_vn(f'{value:,.2f}')}"


def days(value: float) -> str:
    return _vn(f"{value:.1f}") + " ngày"


def change(current, previous):
    if previous is None or previous == 0:
        return None
    ratio = (current - previous) / previous
    return ("+" if ratio >= 0 else "") + pct(ratio)


def highlight(labels, winner) -> list:
    return [ACCENT if label == winner else NEUTRAL for label in labels]


def bar(x, y, colors=None, **kwargs) -> go.Bar:
    marker = dict(color=colors if colors is not None else ACCENT, cornerradius=BAR_RADIUS)
    return go.Bar(x=x, y=y, orientation="h", marker=marker, **kwargs)


def line(x, y, color=ACCENT, hollow=None, **kwargs) -> go.Scatter:
    fill = [SURFACE if h else color for h in hollow] if hollow is not None else color
    return go.Scatter(
        x=x,
        y=y,
        mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=8, color=fill, line=dict(color=color, width=2)),
        **kwargs,
    )


def reference_line(fig: go.Figure, value: float, label: str, vertical: bool = True) -> None:
    opts = dict(line=dict(color=AXIS, width=1))
    if vertical:
        fig.add_vline(x=value, **opts)
        fig.add_annotation(
            x=value, y=1.02, yref="paper", text=label, showarrow=False,
            xanchor="left", xshift=4, font=dict(size=11, color=MUTED),
        )
    else:
        fig.add_hline(y=value, **opts)
        fig.add_annotation(
            y=value, x=1, xref="paper", text=label, showarrow=False,
            yanchor="bottom", xanchor="right", font=dict(size=11, color=MUTED),
        )


def legend_swatches(items) -> str:
    chips = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:.35rem;margin-right:1rem">'
        f'<span style="width:10px;height:10px;border-radius:2px;background:{color};'
        f'display:inline-block"></span><span>{label}</span></span>'
        for label, color in items
    )
    return f'<div style="font-size:.78rem;color:{MUTED};margin-top:.5rem">{chips}</div>'


def show(fig: go.Figure, height: int = 340) -> None:
    fig.update_layout(template="olist", height=height, bargap=BAR_GAP)
    bars = [t for t in fig.data if t.type == "bar"]
    if bars and all(t.orientation == "h" for t in bars):
        fig.update_xaxes(showgrid=True, gridcolor=GRID, showline=False, ticks="")
        fig.update_yaxes(showgrid=False, showline=False)
    st.plotly_chart(fig, config=PLOTLY_CONFIG)


def kpi_row(items: list) -> None:
    for col, item in zip(st.columns(len(items)), items):
        label, value, delta, *rest = item
        delta_color = rest[0] if rest else "normal"
        help_text = rest[1] if len(rest) > 1 else None
        col.metric(label, value, delta, delta_color=delta_color, help=help_text, border=True)

import plotly.graph_objects as go
import plotly.io as pio

SURFACE = "#FFFFFF"
PLANE = "#F7F7F6"
INK = "#0B0B0B"
INK_2 = "#52514E"
MUTED = "#898781"
GRID = "#E1E0D9"
AXIS = "#C3C2B7"
HAIRLINE = "rgba(11, 11, 11, 0.10)"

SERIES = ("#2A78D6", "#EB6834", "#1BAF7A")
ACCENT = SERIES[0]
ACCENT_DEEP = "#184F95"
NEUTRAL = "#C9C8C2"

BLUE_SCALE = [
    [0.00, "#EAF2FD"],
    [0.25, "#9EC5F4"],
    [0.50, "#5598E7"],
    [0.75, "#2A78D6"],
    [1.00, "#0D366B"],
]
TIER_SCALE = ("#184F95", "#3987E5", "#86B6EF")

GOOD = "#0CA30C"
WARNING = "#FAB219"
SERIOUS = "#EC835A"
CRITICAL = "#D03B3B"

FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

SEGMENT_ORDER = (
    "Champions",
    "Loyal Customers",
    "Promising / New Customers",
    "Potential Loyalists",
    "About to Sleep",
    "At Risk / Need Attention",
    "Lost / Hibernating",
)
SEGMENT_TIER = {
    "Champions": "Giá trị cao",
    "Loyal Customers": "Giá trị cao",
    "Promising / New Customers": "Đang phát triển",
    "Potential Loyalists": "Đang phát triển",
    "About to Sleep": "Rủi ro",
    "At Risk / Need Attention": "Rủi ro",
    "Lost / Hibernating": "Rủi ro",
}
TIER_ORDER = ("Giá trị cao", "Đang phát triển", "Rủi ro")
TIER_COLORS = dict(zip(TIER_ORDER, TIER_SCALE))
SEGMENT_COLORS = {s: TIER_COLORS[t] for s, t in SEGMENT_TIER.items()}

PLOTLY_CONFIG = {"displayModeBar": False, "scrollZoom": False}

_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(family=FONT, size=13, color=INK_2),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=4, r=4, t=8, b=4),
        separators=",.",
        colorway=list(SERIES),
        hoverlabel=dict(
            bgcolor=SURFACE,
            bordercolor=AXIS,
            font=dict(family=FONT, size=12, color=INK),
            align="left",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.0,
            x=0,
            font=dict(size=12, color=INK_2),
            itemsizing="constant",
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            linecolor=AXIS,
            linewidth=1,
            ticks="outside",
            ticklen=4,
            tickcolor=AXIS,
            tickfont=dict(size=12, color=MUTED),
            title=dict(font=dict(size=12, color=MUTED), standoff=8),
            automargin=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=GRID,
            gridwidth=1,
            zeroline=False,
            showline=False,
            ticks="",
            tickfont=dict(size=12, color=MUTED),
            title=dict(font=dict(size=12, color=MUTED), standoff=8),
            automargin=True,
        ),
    )
)
pio.templates["olist"] = _TEMPLATE

_CSS_TEMPLATE = """
<style>
  section.main .block-container { padding-top: 2.4rem; max-width: 1480px; }

  .page-head { margin-bottom: .35rem; }
  .page-head h1 {
    font-size: 1.75rem; font-weight: 650; letter-spacing: -.016em;
    color: __INK__; margin: 0 0 .3rem 0; line-height: 1.2;
  }
  .page-lead { color: __INK_2__; font-size: .95rem; max-width: 72ch; margin: 0; }

  .scope {
    display: flex; flex-wrap: wrap; gap: .4rem; align-items: center;
    margin: .85rem 0 .2rem 0; padding: .5rem .7rem;
    background: __PLANE__; border: 1px solid __HAIRLINE__; border-radius: 6px;
  }
  .scope .k {
    font-size: .68rem; font-weight: 650; letter-spacing: .07em;
    text-transform: uppercase; color: __MUTED__; margin-right: .2rem;
  }
  .scope .v {
    font-size: .8rem; color: __INK__; background: __SURFACE__;
    border: 1px solid __HAIRLINE__; border-radius: 4px; padding: .12rem .45rem;
    font-variant-numeric: tabular-nums;
  }
  .scope .v b { font-weight: 600; color: __INK_2__; }

  .eyebrow {
    font-size: .7rem; font-weight: 650; letter-spacing: .09em;
    text-transform: uppercase; color: __MUTED__;
    margin: 1.5rem 0 .55rem 0; padding-bottom: .35rem;
    border-bottom: 1px solid __GRID__;
  }

  .card-head { margin: -.15rem 0 .7rem 0; }
  .card-head .h {
    font-size: 1rem; font-weight: 600; color: __INK__;
    line-height: 1.35; letter-spacing: -.008em;
  }
  .card-head .s { font-size: .8rem; color: __MUTED__; margin-top: .15rem; }
  .card-note { font-size: .78rem; color: __MUTED__; margin-top: .5rem; }

  div[data-testid="stMetric"] { padding: .85rem 1rem; background: __SURFACE__; }
  [data-testid="stMetricLabel"] p {
    font-size: .76rem !important; font-weight: 600; letter-spacing: .02em;
    color: __MUTED__ !important;
  }
  [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important; line-height: 1.3;
  }
  div[data-testid="stMetricValue"] {
    font-size: 1.4rem; font-weight: 640; color: __INK__; letter-spacing: -.02em;
  }
  div[data-testid="stMetricValue"] * { overflow: visible !important; text-overflow: clip !important; }
  div[data-testid="stMetricDelta"] { font-size: .78rem; }

  .provenance {
    margin-top: 2.2rem; padding-top: .8rem; border-top: 1px solid __GRID__;
    font-size: .76rem; color: __MUTED__; line-height: 1.7;
  }
  .provenance b { color: __INK_2__; font-weight: 600; }

  section[data-testid="stSidebar"] .sb-brand {
    font-size: .95rem; font-weight: 650; color: __INK__; letter-spacing: -.01em;
  }
  section[data-testid="stSidebar"] .sb-sub {
    font-size: .74rem; color: __MUTED__; margin-bottom: .6rem;
  }
  [data-testid="stSidebarNav"] { padding-top: .4rem; }
</style>
"""

_TOKENS = (
    ("__SURFACE__", SURFACE),
    ("__PLANE__", PLANE),
    ("__INK_2__", INK_2),
    ("__INK__", INK),
    ("__MUTED__", MUTED),
    ("__GRID__", GRID),
    ("__HAIRLINE__", HAIRLINE),
)

CSS = _CSS_TEMPLATE
for _token, _value in _TOKENS:
    CSS = CSS.replace(_token, _value)

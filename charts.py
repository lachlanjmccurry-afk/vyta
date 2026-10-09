"""
VYTA - Charts for the dashboard (Plotly)
-----------------------------------------
One chart style for every chart: navy and warm grey on white, recessive grid, no Plotly or
Streamlit default colours. Traffic-light colours appear only as the Amber/Red threshold zones
in the indicator drill-down. Show charts with  ui.chart(fig)  (it switches off Streamlit's theme).
"""

import plotly.graph_objects as go
import plotly.io as pio

import score
from report_pdf import RATING_STYLE

NAVY = "#1F3864"
NAVY_MID = "#5A6F96"     # increases in the waterfall
WARM_GREY = "#A8A29A"    # decreases in the waterfall, secondary lines
INK = "#2B2B2B"
MUTED = "#6B665F"
RULE = "#E4E0DA"
GRID = "#EFECE7"
SANS = "'Source Sans Pro', 'Segoe UI', Arial, sans-serif"

pio.templates["vyta"] = go.layout.Template(layout=dict(
    font=dict(family=SANS, size=12, color=INK),
    colorway=[NAVY, WARM_GREY, NAVY_MID, MUTED],
    paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
    margin=dict(l=8, r=8, t=8, b=8),
    xaxis=dict(showgrid=False, linecolor=RULE, ticks="", tickfont=dict(color=MUTED), zeroline=False),
    yaxis=dict(gridcolor=GRID, linecolor=RULE, ticks="", tickfont=dict(color=MUTED), zeroline=False),
    hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=RULE, font=dict(family=SANS, color=INK, size=12)),
    showlegend=False,
))
TEMPLATE = "vyta"

TICKFORMAT = {"percent": ".0%", "percentage_points": "+.0%"}


def money(x):
    return score.money(x)


def sparkline(points):
    """A tiny trend line for the Indicators table: no axes, latest point marked."""
    xs = [m for m, _ in points]
    ys = [v for _, v in points]
    fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=NAVY, width=2), connectgaps=False,
                               hoverinfo="skip"))
    last = next(((m, v) for m, v in reversed(points) if v is not None), None)
    if last:
        fig.add_trace(go.Scatter(x=[last[0]], y=[last[1]], mode="markers", hoverinfo="skip",
                                 marker=dict(color=NAVY, size=6, line=dict(color="#FFFFFF", width=1.5))))
    fig.update_layout(template=TEMPLATE, height=34, margin=dict(l=2, r=6, t=4, b=4),
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def zones(ind, low, high):
    """(y0, y1, rating) background bands for the Amber and Red zones, following the indicator's direction."""
    amber, red = ind["amber"], ind["red"]
    if ind["direction"] == "higher_is_worse":
        return [(amber, red, "Amber"), (red, high, "Red")]
    return [(red, amber, "Amber"), (low, red, "Red")]


def trend_chart(points, ind):
    """Full 12-month trend with the Amber and Red zones shaded behind the line."""
    unit = ind.get("unit", "ratio")
    xs = [m for m, _ in points]
    ys = [v for _, v in points]
    known = [v for v in ys if v is not None] + [ind["amber"], ind["red"]]
    span = (max(known) - min(known)) or abs(max(known)) or 1
    low, high = min(known) - span * 0.15, max(known) + span * 0.15

    fig = go.Figure()
    for y0, y1, rating in zones(ind, low, high):
        fig.add_hrect(y0=y0, y1=y1, fillcolor=RATING_STYLE[rating][0], opacity=0.55, line_width=0, layer="below")
    for key, label in (("amber", "Amber"), ("red", "Red")):
        fig.add_hline(y=ind[key], line=dict(color=WARM_GREY, width=1, dash="dot"), layer="below",
                      annotation=dict(text=f"{label} at {score.fmt(ind[key], unit)}", font=dict(color=MUTED, size=11),
                                      bgcolor="rgba(255,255,255,0.7)"),
                      annotation_position="top left")
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines+markers", connectgaps=False,
        line=dict(color=NAVY, width=2), marker=dict(color=NAVY, size=8, line=dict(color="#FFFFFF", width=2)),
        customdata=[score.fmt(v, unit) if v is not None else "" for v in ys],
        hovertemplate="%{x|%b %Y}<br><b>%{customdata}</b><extra></extra>"))
    fig.update_layout(template=TEMPLATE, height=320, margin=dict(l=8, r=8, t=12, b=8), hovermode="x",
                      yaxis=dict(range=[low, high], tickformat=TICKFORMAT.get(unit, ",.2~f")),
                      xaxis=dict(tickformat="%b %y", dtick="M1" if len(xs) <= 12 else "M2"))
    return fig


def waterfall(bridge):
    """Opening cash -> each step -> closing cash. Totals navy, increases mid-navy, decreases warm grey;
    every bar carries a signed label so direction never depends on colour."""
    labels = [f"Opening<br>{bridge['opening_month']:%b %Y}"] + [l.replace(" ", "<br>", 1) if len(l) > 12 else l
                                                                for l, _ in bridge["steps"]] \
        + [f"Closing<br>{bridge['closing_month']:%b %Y}"]
    amounts = [bridge["opening"]] + [v for _, v in bridge["steps"]] + [bridge["closing"]]
    measure = ["absolute"] + ["relative"] * len(bridge["steps"]) + ["total"]
    text = [money(bridge["opening"])] + [("+" if v >= 0 else "") + money(v) for _, v in bridge["steps"]] \
        + [money(bridge["closing"])]
    fig = go.Figure(go.Waterfall(
        x=labels, y=amounts, measure=measure, text=text, textposition="outside",
        textfont=dict(color=INK, size=12), cliponaxis=False,
        totals=dict(marker=dict(color=NAVY, line=dict(width=0))),
        increasing=dict(marker=dict(color=NAVY_MID, line=dict(width=0))),
        decreasing=dict(marker=dict(color=WARM_GREY, line=dict(width=0))),
        connector=dict(line=dict(color=RULE, width=1)),
        customdata=text, hovertemplate="%{x}<br><b>%{customdata}</b><extra></extra>"))
    fig.update_layout(template=TEMPLATE, height=380, margin=dict(l=8, r=8, t=28, b=8), bargap=0.35,
                      yaxis=dict(tickprefix="$", tickformat="~s"),
                      xaxis=dict(tickfont=dict(color=INK, size=12)))
    return fig


def score_history(snaps, kind, bands):
    """One score (0-100) across the saved snapshots, with the band boundaries as dotted lines.
    One chart per score: Distress and Viability point in opposite directions, so they never share a chart."""
    xs = [s["_taken"] for s in snaps]
    ys = [s[kind]["score"] for s in snaps]
    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="lines+markers", connectgaps=False, line=dict(color=NAVY, width=2),
        marker=dict(color=NAVY, size=8, line=dict(color="#FFFFFF", width=2)),
        customdata=[f"{s[kind]['score']:.1f} · {s[kind]['band']}" if s[kind]["score"] is not None
                    else s[kind]["band"] for s in snaps],
        hovertemplate="%{x|%d %b %Y, %H:%M}<br><b>%{customdata}</b><extra></extra>"))
    for b in bands:
        if b["from"] > 0:
            fig.add_hline(y=b["from"], line=dict(color=WARM_GREY, width=1, dash="dot"), layer="below",
                          annotation=dict(text=f"{b['band']} from {b['from']}", font=dict(color=MUTED, size=11),
                                          bgcolor="rgba(255,255,255,0.7)"),
                          annotation_position="top left")
    fig.update_layout(template=TEMPLATE, height=240, hovermode="x", yaxis=dict(range=[0, 100], dtick=20),
                      xaxis=dict(tickformat="%d %b"))
    return fig


def cash_line(months):
    """Month-end cash balance over the period, for context under the waterfall."""
    xs = [m["month"] for m in months]
    ys = [m["cash"] for m in months]
    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="lines+markers", line=dict(color=NAVY, width=2),
        marker=dict(color=NAVY, size=8, line=dict(color="#FFFFFF", width=2)),
        customdata=[money(v) for v in ys], hovertemplate="%{x|%b %Y}<br><b>%{customdata}</b><extra></extra>"))
    if min(ys) < 0 < max(ys):
        fig.add_hline(y=0, line=dict(color=WARM_GREY, width=1))
    fig.update_layout(template=TEMPLATE, height=240, hovermode="x",
                      yaxis=dict(tickprefix="$", tickformat="~s"),
                      xaxis=dict(tickformat="%b %y", dtick="M1" if len(xs) <= 13 else "M2"))
    return fig

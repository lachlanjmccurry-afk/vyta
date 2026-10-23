"""Overview page: verdict, data confidence, the two scores with their band bars, the recommended pathway,
top 3 issues and what's working. Every number comes from score.py (via ui.current_run())."""

import streamlit as st

import score
import ui
from report_pdf import BAND_RATING
from ui import esc, md

run = ui.current_run()
results = run["results"]
text = ui.wording().get("overview_page", {})


def band_bar(kind, value):
    """Coloured segments sized by the band ranges in scorecard.json, with a marker at the score."""
    bands = sorted(run["cfg"]["bands"][kind], key=lambda b: b["from"])
    edges = [b["from"] for b in bands] + [100]
    widths = [max(0, edges[i + 1] - edges[i]) for i in range(len(bands))]
    segs = "".join(f"<b style='flex:{w};background:{ui.BAR[BAND_RATING.get(b['band'], 'Not assessed')]}'></b>"
                   for b, w in zip(bands, widths))
    marker = "" if value is None else f"<i style='left:{min(100, max(0, value)):.1f}%'></i>"
    ticks = "".join(f"<span style='flex:{w}'>{esc(b['band'])}</span>" for b, w in zip(bands, widths))
    return f"<div class='vy-bar'>{segs}{marker}</div><div class='vy-ticks'>{ticks}</div>"


def score_card(kind):
    value = run["scores"][kind][0]
    band = run["bands"][kind]
    shown = "&ndash;" if value is None else f"{value:.0f}"
    return (f"<div class='vy-panel vy-score'><div class='top'><div>"
            f"<div class='q'>{esc(text.get(kind + '_question', kind.title()))}</div>"
            f"<div class='s'>{esc(text.get(kind + '_sub', ''))}</div></div>{ui.band_pill(band)}</div>"
            f"<div class='big'>{shown}<span>/ 100</span></div>{band_bar(kind, value)}</div>")


def bullet_list(items):
    rows = []
    for r in items:
        value = r.get("display", "")
        rows.append(f"<div class='vy-li'><span class='d' style='background:{ui.MARKER[score_rating(r)]}'></span><div>"
                    f"<div class='t'>{esc(r['ind'].get('name', ''))}"
                    f"{f' <span class=v>· {esc(value)}</span>' if value else ''}</div>"
                    f"<div class='x'>{esc(ui.first_sentence(r.get('explanation') or r.get('note', '')))}</div></div></div>")
    return "".join(rows)


def score_rating(r):
    return r["rating"] if r["rating"] in ui.MARKER else "Not assessed"


def list_card(key, title, items, empty, link=None):
    with st.container(key=f"card-{key}"):
        left, right = st.columns([3, 2], vertical_alignment="center")
        with left:
            md(f"<div class='vy-cardhead'>{esc(title)}</div>")
        if link:
            with right:
                st.page_link("app/views/details.py", label=link)
        md(bullet_list(items) if items else f"<div class='vy-sub'>{esc(empty)}</div>")


ui.page_head(text.get("eyebrow", "Overview"), run["verdict"])
for problem in run["problems"]:
    st.warning(f"wording.json: {problem}")

conf = run["confidence"]
md(f"<div class='vy-banner {esc(conf['level'])}'><span class='i'>{'i' if conf['level'] == 'High' else '!'}</span>"
   f"<div><b>{esc(text.get('confidence', {}).get(conf['level'], conf['level'] + ' data confidence.'))}</b> "
   f"{esc(conf['text'])}</div></div>")

a, b = st.columns(2, gap="medium")
with a:
    md(score_card("distress"))
with b:
    md(score_card("viability"))

applied = [n.replace("APPLIED: ", "") for n in run["override_notes"] if n.startswith("APPLIED")]
with st.container(key="vy-pathway"):
    left, right = st.columns([3, 1.1], vertical_alignment="center")
    with left:
        md(f"<div class='vy-path'><div class='e'>{esc(text.get('pathway_eyebrow', 'Recommended pathway'))}</div>"
           f"<div class='t'>{esc(run['pathway_label'])}</div><div class='x'>{esc(run['summary'])}</div>"
           + (f"<div class='o'>{esc(text.get('override', ''))} {esc(' '.join(applied))}</div>" if applied else "")
           + "</div>")
    with right:
        st.page_link("app/views/get_help.py", label=f"{text.get('pathway_button', 'See matched advisers')} →")

left, right = st.columns(2, gap="medium")
with left:
    list_card("issues", text.get("issues_title", "Top 3 issues"), score.top_issues(results),
              text.get("issues_none", ""), link=text.get("issues_link", "All {count} indicators").format(count=len(results)))
with right:
    list_card("working", text.get("working_title", "What's working"), score.whats_working(results),
              text.get("working_none", ""))

md(f"<div class='vy-foot'>{esc(text.get('footer', ''))}</div>")

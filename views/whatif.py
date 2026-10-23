"""What if? page: sliders for a few changes to the business, with both scores, bands and the pathway
recalculated live (whatif.py, scored by score.score_data) and shown before -> after."""

import streamlit as st

import score
import ui
import whatif
from report_pdf import BAND_RATING
from ui import esc, md

run = ui.current_run()
base = run.get("unsteadied", run)  # compare against this month's own figures, not a held band
text = run["wording"].get("whatif_page", {})

# (key, label, min, max, step, format, help) - percentages are entered as whole numbers
SLIDERS = [
    ("price", "Price / margin increase (%)", 0, 30, 1, "%d%%", "Higher prices on the same sales; costs unchanged"),
    ("revenue", "Revenue change (%)", -30, 30, 1, "%d%%", "More or fewer sales: cost of sales moves with them"),
    ("cost_of_sales", "Cost of sales reduction (%)", 0, 30, 1, "%d%%", "Cheaper direct costs"),
    ("overhead", "Overhead reduction (%)", 0, 30, 1, "%d%%", "Lower operating expenses"),
    ("debtor_days", "Days faster debtor collection", 0, 60, 5, "%d days", "Customers pay this many days sooner"),
]
PERCENT = {"price", "revenue", "cost_of_sales", "overhead"}


def reset():
    for key, *_ in SLIDERS:
        st.session_state[f"wi_{key}"] = 0
    st.session_state["wi_ato_plan"] = False


def marker(band):
    return f"<span class='vy-dot' style='background:{ui.MARKER[BAND_RATING.get(band, 'Not assessed')]}'></span>"


def score_card(kind, before, after):
    s0, s1 = before["scores"][kind][0], after["scores"][kind][0]
    b0, b1 = before["bands"][kind], after["bands"][kind]
    num = lambda s: "n/a" if s is None else f"{s:.0f}"
    delta = "" if s0 is None or s1 is None or round(s1) == round(s0) else f"{round(s1) - round(s0):+d}"
    return f"""
    <div class="vy-card">
      <div class="label">{kind.title()}</div>
      <div class="num">{num(s0)}<span class="arrow">&rarr;</span>{num(s1)}<span> / 100</span></div>
      <div class="band">{marker(b0)}{esc(b0)} <span class="arrow">&rarr;</span> {marker(b1)}{esc(b1)}</div>
      <div class="hint">{f'Change: {delta} points' if delta else 'No change in score'}</div>
    </div>"""


for key, *_ in SLIDERS:                       # starting values live only in session state (Reset sets them)
    st.session_state.setdefault(f"wi_{key}", 0)
st.session_state.setdefault("wi_ato_plan", False)

ui.page_head("What if?", text.get("heading", "What if?"))
md(f"<div class='vy-sub'>{esc(text.get('intro', ''))}</div>")

with st.container(border=True, key="wi-levers"):
    cols = st.columns(3, gap="medium")
    levers = {}
    for i, (key, label, lo, hi, step, fmt, help_text) in enumerate(SLIDERS):
        with cols[i % 3]:
            v = st.slider(label, lo, hi, step=step, format=fmt, help=help_text, key=f"wi_{key}")
            levers[key] = v / 100 if key in PERCENT else v
    with cols[len(SLIDERS) % 3]:
        levers["ato_plan"] = st.toggle("ATO payment plan", key="wi_ato_plan",
                                       help="Spread the current ATO debt over 12 monthly instalments")
        st.button("Reset", on_click=reset, type="tertiary", icon=":material/restart_alt:", key="wi_reset")

after = whatif.run(run, levers)

a, b = st.columns(2, gap="medium")
with a:
    md(score_card("distress", base, after))
with b:
    md(score_card("viability", base, after))

p0, p1 = score.sentence_case(base["pathway"]), score.sentence_case(after["pathway"])
md(f"""<div class="vy-conf"><b>Pathway:</b> {esc(p0)}""" +
   ("" if p0 == p1 else f" <span class='arrow'>&rarr;</span> <b>{esc(p1)}</b>") + "</div>")
md(f"<div class='vy-verdict' style='font-size:1.45rem;margin:var(--s5) 0 0'>"
   f"{esc(whatif.describe(levers, base, after, text))}</div>")

ui.heading(text.get("changes_title", "Indicators that change colour"))
changes = whatif.changed_indicators(run, after)
if changes:
    rows = "".join(
        f"<tr><td class='muted'>{esc(r0['ind']['id'])}</td><td>{esc(score.short_name(r0['ind']))}</td>"
        f"<td>{ui.pill(r0)} <span class='muted'>{esc(r0.get('display', ''))}</span></td>"
        f"<td class='muted'>&rarr;</td>"
        f"<td>{ui.pill(r1)} <span class='muted'>{esc(r1.get('display', ''))}</span></td></tr>"
        for r0, r1 in changes)
    md("<div class='vy-scroll'><table class='vy-table'><tr><th>ID</th><th>Indicator</th><th>Now</th><th></th>"
       f"<th>What if</th></tr>{rows}</table></div>")
else:
    md(f"<div class='vy-sub'>{esc(text.get('no_changes', ''))}</div>")

md(f"<div class='vy-note' style='margin-top:var(--s5)'>{esc(text.get('assumptions', ''))}</div>")

"""Overview page: the adviser's one-page memo (verdict, scores, top issues, what's working, pathway)."""

from datetime import date

import streamlit as st

import score
import ui
from report_pdf import BAND_RATING, build_pdf
from ui import esc, md

run = ui.current_run()
d, results = run["d"], run["results"]


def score_card(kind):
    s, weight, possible, _ = run["scores"][kind]
    band = run["bands"][kind]
    marker = ui.MARKER[BAND_RATING.get(band, "Not assessed")]
    meaning = "Higher means more distress" if kind == "distress" else "Higher means more viable"
    noun = "distress" if kind == "distress" else "viability"
    return f"""
    <div class="vy-card">
      <div class="label">{kind.title()}</div>
      <div class="num">{'n/a' if s is None else f'{s:.0f}'}<span> / 100</span></div>
      <div class="band"><span class="vy-dot" style="background:{marker}"></span>{esc(band)} {noun}</div>
      <div class="hint">{meaning} · {weight:g} of {possible:g} weight points assessed</div>
    </div>"""


def memo_list(items, numbered):
    rows = []
    for i, r in enumerate(items, start=1):
        ind = r["ind"]
        rows.append(f"""
        <div class="vy-item">
          <div class="n">{i if numbered else '&#10003;'}</div>
          <div><span class="t">{esc(ind.get('name', ''))}</span>{ui.pill(r)}
            <span class="v">{esc(r.get('display', ''))}</span>
            <div class="x">{esc(r.get('explanation') or r.get('note', ''))}</div></div>
        </div>""")
    return "".join(rows)


left, right = st.columns([4, 1], vertical_alignment="top")
with left:
    ui.masthead(run)
with right:
    slug = "".join(c if c.isalnum() else "_" for c in d["org"]).strip("_").lower()
    st.download_button("Export PDF", data=build_pdf(run), icon=":material/download:", width="stretch",
                       file_name=f"vyta_report_{slug}_{date.today():%Y-%m-%d}.pdf", mime="application/pdf")

md(f"<div class='vy-verdict'>{esc(run['verdict'])}</div>")
for problem in run["problems"]:
    st.warning(f"wording.json: {problem}")

a, b = st.columns(2, gap="medium")
with a:
    md(score_card("distress"))
with b:
    md(score_card("viability"))

conf = run["confidence"]
md(f"<div class='vy-conf'><b>Data confidence: {esc(conf['level'])}.</b> {esc(conf['text'])}</div>")

issues = score.top_issues(results)
ui.heading("Top 3 issues")
md(memo_list(issues, numbered=True) if issues else "<div class='vy-sub'>No indicators are flagged Red or Amber.</div>")

working = score.whats_working(results)
ui.heading("What's working")
md(memo_list(working, numbered=False) if working else "<div class='vy-sub'>Nothing is rated Green yet.</div>")

applied = [n for n in run["override_notes"] if n.startswith("APPLIED")]
override = " ".join(applied or run["override_notes"]) or "none set up"
ui.heading("Recommended pathway")
md(f"""<div class="vy-path">
  <div class="label">{esc(score.sentence_case(run['pathway']))}</div>
  <div class="x">{esc(run['summary'])}</div>
</div>
<div class="vy-note">Statutory demand override: {esc(override)}</div>""")

flagged = sum(1 for r in results if r["rating"] in score.SEVERITY)
skipped = sum(1 for r in results if r["points"] is None)
md(f"<div class='vy-note' style='margin-top:var(--s6)'>{flagged} indicators are Red or Amber and "
   f"{skipped} couldn't be assessed. See the Indicators page for every indicator.<br>"
   f"{esc(run['cfg'].get('disclaimer', ''))}</div>")

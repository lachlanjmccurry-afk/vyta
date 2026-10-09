"""Owner questions page: the questions only the owner can answer (from scorecard.json), the indicators
waiting on owner input, and the statutory demand override. Read-only - answers go in scorecard.json."""

import score
import ui
from ui import esc, md

run = ui.current_run()
text = ui.wording().get("owner_questions_page", {})

ui.masthead(run, "Owner questions")
md(f"<div class='vy-sub'>{esc(text.get('intro', ''))}</div>")

rows = []
for q in run["cfg"].get("owner_questions", []):
    answer = q.get("answer")
    shown = (f"<td class='muted'>{esc(text.get('not_answered', 'Not answered yet'))}</td>"
             if answer in (None, "") else f"<td><b>{esc(answer)}</b></td>")
    rows.append(f"<tr><td class='muted'>{esc(q['id'])}</td><td>{esc(q['question'])}</td>"
                f"<td class='muted'>{esc(q.get('feeds', ''))}</td>{shown}</tr>")
md("<div class='vy-scroll'><table class='vy-table'><tr><th>#</th><th>Question</th><th>Feeds into</th>"
   f"<th>Answer</th></tr>{''.join(rows)}</table></div>")
md(f"<div class='vy-note'>{esc(text.get('how_to_answer', ''))}</div>")

ui.heading(text.get("waiting_title", "Indicators waiting on owner input"))
waiting = [r for r in run["results"] if r["rating"] == score.OWNER_QUESTION]
if waiting:
    items = "".join(f"<div class='vy-item'><div class='n'>{esc(r['ind']['id'])}</div><div>"
                    f"<span class='t'>{esc(r['ind'].get('name', ''))}</span>"
                    f"<div class='x'>{esc(r.get('note', ''))}</div></div></div>" for r in waiting)
    md(items)
else:
    md(f"<div class='vy-sub'>{esc(text.get('waiting_none', ''))}</div>")

ui.heading(text.get("override_title", "Statutory demand override"))
md("".join(f"<div class='vy-cell' style='margin-bottom:var(--s2)'>{esc(n)}</div>" for n in run["override_notes"])
   or "<div class='vy-sub'>None set up.</div>")

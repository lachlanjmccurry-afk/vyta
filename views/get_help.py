"""Get help page: advisers from firms.json (fictional demo listings) that serve this business's pathway,
filtered by adviser type, with "Listed partner" labels and a "Why matched" line built from the indicator
results (firms.py). Contact / View profile open a window with the (placeholder) details. Read-only."""

import streamlit as st

import firms
import ui
from ui import esc, md

run = ui.current_run()
text = ui.wording().get("help_page", {})
data = firms.load()
types = data.get("types", {})
by_id = {f["id"]: f for f in data.get("firms", [])}


@st.dialog("Contact")
def contact(firm):
    md(f"<div class='vy-cardhead'>{esc(firm['name'])}</div><div class='vy-sub'>{esc(firm.get('type_label', ''))}</div>")
    md(f"<div class='vy-facts' style='font-size:.9rem'><span class='f'>Contact</span><span>{esc(firm.get('contact_name', ''))}</span>"
       f"<span class='f'>Phone</span><span>{esc(firm.get('phone', ''))}</span>"
       f"<span class='f'>Email</span><span>{esc(firm.get('email', ''))}</span></div>")
    md(f"<div class='vy-note'>{esc(text.get('privacy_note', ''))}<br>{esc(text.get('sample_note', ''))}</div>")


@st.dialog("Profile", width="large")
def profile(firm):
    md(f"<div class='vy-cardhead'>{esc(firm['name'])}</div><div class='vy-sub'>{esc(firm.get('type_label', ''))} · "
       f"{esc(firm.get('city', ''))}, {esc(firm.get('state', ''))}</div>")
    md(f"<div class='vy-cell' style='line-height:1.6'>{esc(firm.get('about', ''))}</div>")
    md(f"<div class='vy-note'><b>{esc(text.get('helps', 'Helps with'))}:</b> {esc(firm.get('helps_with', ''))}</div>")
    md(f"<div class='vy-note'>{esc(text.get('sample_note', ''))}</div>")


@st.dialog("Get listed")
def apply():
    md(f"<div class='vy-cell' style='line-height:1.6'>{esc(text.get('apply_text', ''))}</div>")


def card_html(f):
    bg, fg = f.get("colours", ["#EEF0F3", "#344054"])
    tag = f"<span class='tag'>{esc(text.get('partner', 'Listed partner'))}</span>" if f.get("listed_partner") else ""
    badge = f"<div class='badge'>✓ {esc(f['badge'])}</div>" if f.get("badge") else ""
    return (f"<div class='vy-firm'><div class='head'><div class='av' style='background:{esc(bg)};color:{esc(fg)}'>"
            f"{esc(f.get('initials', ''))}</div>{tag}</div>"
            f"<div class='nm'>{esc(f['name'])}</div><div class='ty'>{esc(f.get('type_label', ''))}</div>{badge}"
            f"<div class='p'>{esc(text.get('helps', 'Helps with'))} {esc(f.get('helps_with', ''))}</div>"
            f"<div class='p' style='margin-top:4px'>{esc(text.get('location', 'Location'))} "
            f"{esc(f.get('city', ''))}, {esc(f.get('state', ''))}</div>"
            f"<div class='why'><b>{esc(text.get('why', 'Why matched:'))}</b> {esc(f['why_text'])}</div></div>")


left, right = st.columns([3, 1.2], vertical_alignment="bottom")
with left:
    ui.page_head(text.get("eyebrow", "Get help"), text.get("title", "Advisers"), text.get("intro"))
with right:
    md(f"<div class='vy-yourpath' style='margin-bottom:var(--s5)'>{esc(text.get('your_pathway', 'Your pathway'))}"
       f"<b>{esc(run['pathway_label'])}</b></div>")

options = ["all"] + list(types)
choice = st.pills("Adviser type", options, default="all", key="help_filter", label_visibility="collapsed",
                  format_func=lambda k: text.get("all", "All matches") if k == "all" else types[k]) or "all"

matched = firms.matches(run, data, state=firms.business_state(run["base"]),
                        kind=None if choice == "all" else choice)
if not matched:
    md(f"<div class='vy-panel vy-sub'>{esc(text.get('none', ''))}</div>")
for start in range(0, len(matched), 3):
    cols = st.columns(3, gap="medium")
    for col, f in zip(cols, matched[start:start + 3]):
        with col, st.container(key=f"card-firm-{f['id']}"):
            md(card_html(f))
            a, b = st.columns(2, gap="small")
            with a:
                if st.button(text.get("contact", "Contact"), key=f"contact-{f['id']}", type="primary", width="stretch"):
                    contact(by_id[f["id"]])
            with b:
                if st.button(text.get("profile", "View profile"), key=f"profile-{f['id']}", width="stretch"):
                    profile(by_id[f["id"]])

st.write("")
left, right = st.columns([1.3, 1], gap="medium")
with left:
    md(f"<div class='vy-panel vy-how' style='height:100%'><svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='#0E7C6B' stroke-width='2' "
       f"stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><rect x='4' y='11' width='16' height='10' rx='2'/>"
       f"<path d='M8 11V7a4 4 0 0 1 8 0v4'/></svg><div>"
       f"<div class='t'>{esc(text.get('how_title', ''))}</div><div class='x'>{esc(text.get('how_text', ''))}</div></div></div>")
with right, st.container(key="vy-adviser"):
    md(f"<div class='vy-adv' id='get-listed'><div class='t'>{esc(text.get('adviser_title', ''))}</div>"
       f"<div class='x'>{esc(text.get('adviser_text', ''))}</div></div>")
    if st.button(text.get("apply", "Apply to be listed"), key="apply"):
        apply()

md(f"<div class='vy-foot'>{esc(text.get('footer', ''))}</div>")

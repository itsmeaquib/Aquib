#!/usr/bin/env python3
"""
Build the QBS shift handover email as an UNSENT .eml draft (+ HTML paste-fallback)
from a JSON file of confirmed tickets. Nothing is hardcoded about the tickets.

Usage:
    python3 build_handover_eml.py --input tickets.json [--output-dir /mnt/user-data/outputs]

tickets.json:
{
  "date": "2026-11-05",
  "sender_name": "Aquib Javed Shaikh",
  "sender_addr": "aquib.shaikh@quorumsoftware.com",
  "tickets": [
    {"id": 1900738, "title": "...", "priority": "P2 – Major",   # P1 – Critical | P2 – Major | P3 – Minor | P4 – Trivial
     "medium": false,                 # true if Custom.Priority2 was "Medium" (shown as P3 + footnote)
     "state": "Additional Information Required",
     "updated": "2026-11-05 10:14",   # latest comment createdDate, UTC, YYYY-MM-DD HH:MM
     "assignee": "Aquib Javed Shaikh",# confirmed name, NEVER blank
     "next_action": "...",
     "partial": "10 of 23"            # optional: only part of the comments were reviewed
    }
  ]
}

Output: QBS_Shift_Handover_<date>.eml  (X-Unsent: 1, To/Cc absent, no attachment, no images)
        QBS_Shift_Handover_<date>.html (same body, for copy-paste into Outlook)
The script never sends anything.
"""
import argparse, html as h, json, os, sys
from email.mime.text import MIMEText

BASE = "https://quorumsoftware.visualstudio.com/myQuorum%20Cloud/_workitems/edit/"
COLS = ["ID", "Title", "Priority", "State", "Last Updated (UTC)", "Assignee", "Next Action"]
TH = "border:2px solid #000;padding:6px;background:#1F3864;color:#ffffff;font-weight:bold;text-align:left;"
TD = "border:2px solid #000;padding:6px;vertical-align:top;"
FONT = "font-family:Calibri,Arial,sans-serif;"
P = f"margin:0 0 10px 0;{FONT}font-size:14px;color:#000;"


def rank(t):
    return 0 if t["priority"].startswith("P1") else 1 if t["priority"].startswith("P2") else 2


def row_html(t):
    if t["priority"].startswith("P1"):
        bg, pc = "background:#FEE8E8;", "color:#CC0000;font-weight:bold;"
    elif t["priority"].startswith("P2"):
        bg, pc = "background:#FFFBEB;", "color:#B45309;font-weight:bold;"
    else:
        bg, pc = "", ""
    prio = t["priority"] + ("*" if t.get("medium") else "")
    nxt = t["next_action"] + (" \u2020" if t.get("partial") else "")
    vals = [f'<a href="{BASE}{t["id"]}">{t["id"]}</a>', h.escape(t["title"]), h.escape(prio),
            h.escape(t["state"]), h.escape(t["updated"]), h.escape(t["assignee"]), h.escape(nxt)]
    cells = []
    for i, v in enumerate(vals):
        extra = pc if i == 2 else ("font-weight:bold;" if i == 6 else "")
        cells.append(f'<td style="{TD}{bg}{extra}">{v}</td>')
    return "<tr>" + "".join(cells) + "</tr>"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output-dir", default="/mnt/user-data/outputs")
    a = ap.parse_args()
    d = json.load(open(a.input, encoding="utf-8"))

    tickets = d["tickets"]
    for t in tickets:
        if not str(t.get("assignee", "")).strip():
            sys.exit(f"Ticket {t['id']}: assignee is blank. SOP: Assignee must always be filled.")
    # P1, then P2, then the rest; within each group newest comment first
    tickets = sorted(tickets, key=lambda t: t["updated"], reverse=True)
    tickets = sorted(tickets, key=rank)

    total = len(tickets)
    p1 = sum(rank(t) == 0 for t in tickets)
    p2 = sum(rank(t) == 1 for t in tickets)
    date = d["date"]

    table = (f'<table style="border-collapse:collapse;width:100%;{FONT}font-size:13px;border:2px solid #000;">'
             "<thead><tr>" + "".join(f'<th style="{TH}">{c}</th>' for c in COLS) + "</tr></thead>"
             "<tbody>" + "".join(row_html(t) for t in tickets) + "</tbody></table>")

    notes = []
    if any(t.get("medium") for t in tickets):
        notes.append("* Custom.Priority2 is &ldquo;Medium&rdquo; (non-standard) in ADO and is shown as P3 &ndash; Minor; "
                     "recommend reclassifying in ADO.")
    for t in tickets:
        if t.get("partial"):
            notes.append(f"&dagger; #{t['id']}: only {h.escape(t['partial'])} comments were reviewed for this Next Action.")
    notes.append("Last Updated is the time of the latest comment on the ticket (UTC).")
    foot = f'<p style="margin:6px 0 14px 0;{FONT}font-size:11px;color:#555;">' + "<br>".join(notes) + "</p>"

    body = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>QBS Shift Handover</title></head>
<body style="margin:0;padding:0;background:#ffffff;">
<p style="{P}">Hi Team,</p>
<p style="{P}">Please find the QBS shift handover for <b>{h.escape(date)}</b>. We currently have <b>{total}</b> active tickets: <b>{p1}</b> P1 Critical and <b>{p2}</b> P2 Major. Please prioritise any P1 Critical and P2 Major items first. The Next Action column lists what needs to happen next for each ticket.</p>
{table}
{foot}
<p style="{P}">Thanks &amp; Regards,<br>{h.escape(d['sender_name'])}</p>
</body></html>"""

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = f"QBS Shift Handover \u2013 {date}"
    msg["From"] = f"{d['sender_name']} <{d['sender_addr']}>"
    msg["X-Unsent"] = "1"  # opens as an editable new message in desktop Outlook; To/Cc intentionally absent

    os.makedirs(a.output_dir, exist_ok=True)
    eml = os.path.join(a.output_dir, f"QBS_Shift_Handover_{date}.eml")
    htm = os.path.join(a.output_dir, f"QBS_Shift_Handover_{date}.html")
    open(eml, "wb").write(msg.as_bytes())
    open(htm, "w", encoding="utf-8").write(body)
    print(f"Wrote {eml}\nWrote {htm}\nTickets: {total} | P1: {p1} | P2: {p2}")


if __name__ == "__main__":
    main()

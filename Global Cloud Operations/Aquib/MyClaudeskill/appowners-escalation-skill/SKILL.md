---
name: appowners-escalation-skill
description: Generates a structured ESCALATION TEMPLATE from an Azure DevOps work item in the myQuorum Cloud project. Use this whenever Aquib gives a bare WI/ticket number and asks to "escalate", "generate escalation template", "fill escalation template", "prep escalation notes", "create escalation", or "esc [number]" — this is a read-only template-generation workflow, distinct from the incident-resolution or ticket-escalation-creation skills which write back to ADO. Fetches the work item and its comments, extracts issue details/logs/troubleshooting history, converts all timestamps to CST, and renders a fixed 5-section escalation template ready to paste and send to application owners. Always trigger proactively even if the user just pastes a WI number with no other context.
---

# Escalation Template Generator

Read-only workflow that turns an Azure DevOps work item into a polished, copy-ready escalation
template for application owners and senior stakeholders. This skill **never modifies the WI and
never posts comments** — it only reads and renders.

## Step 1 — Fetch the Work Item

Given a WI ID, make both calls before doing anything else (comments are never included in the
expand payload, so both are always required):

1. `wit_get_work_item` — params: `id` (integer), `project: myQuorum Cloud`, `expand: all`
2. `wit_list_work_item_comments` — params: `workItemId` (integer), `project: myQuorum Cloud`
   (optionally `top: 50`)

If these tools are unreachable, ask the user to paste the WI content (description + comments)
manually instead of retrying repeatedly.

## Step 2 — Extract Fields

| Template Field | Source in WI |
|---|---|
| User Impacted | Description, title, comments |
| Steps to Reproduce | Description or comments |
| What Customer Sees | Description, screenshot references |
| Frequency / Scope | Description, priority, outage fields |
| Date / Time / Duration | CreatedDate, ChangedDate, comment timestamps — **convert all to CST** |
| Logs | Attachments listed; comments referencing log files (include filename + upload time if available) |
| Server Resources | Comments referencing CPU/RAM/Disk, Azure Monitor, SolarWinds |
| Troubleshooting Steps | All comments, chronologically — flag service restarts, server restarts, log review findings |

**Timestamps:** All ADO timestamps are UTC. Convert to CST (UTC−6) or CDT (UTC−5 during daylight
saving) before use anywhere in the template. A simple Python `datetime` subtraction is reliable
for this.

**Inline screenshots:** Images embedded in ADO fields/comments only resolve to GUIDs via the API.
Never guess or describe their content — flag them as requiring direct review in the ADO UI.

**AI Triage box:** If the WI has an AI Triage section, treat its log analysis as a primary
reference source for the template, not a supplementary note.

**Never invent data.** Use `[Not documented – follow up needed]` for anything missing. If there
are no comments, note: "No troubleshooting activity logged in WI comments."

## Step 3 — Render the Template

Output exactly this structure (fill in bracketed fields, keep the layout/separators intact):

```
═══════════════════════════════════════════════════════════════
                      ESCALATION TEMPLATE
  WI #[ID] — [Title]   |   Generated: [Date Time CST]
═══════════════════════════════════════════════════════════════

📋 ISSUE IDENTIFICATION
──────────────────────────────────────────────────────────────
- User Impacted / Username / User ID:
- Steps to Reproduce:
- What Does the Customer See? (Screenshots):
- Frequency / Scope (All users / Some users / One user):
- Date / Time / Timeframe / Duration:

📁 LOGS & RESOURCES
──────────────────────────────────────────────────────────────
- Logs: (Collect before any restart)
  - [filename — uploaded: date/time CST]
- Server Resource Collection (CPU, RAM, Disk):
  [Current state | Azure Monitor / SolarWinds historical]

🔧 TROUBLESHOOTING STEPS
──────────────────────────────────────────────────────────────
- Service Restarts?   [Yes — service, date/time CST | No]
- Server Restarts?    [Yes — server, date/time CST | No]
- Log Review & Findings:
- Additional Steps Taken (chronological):

📝 ADDITIONAL NOTES
──────────────────────────────────────────────────────────────

⚠️  OPEN ITEMS / GAPS
──────────────────────────────────────────────────────────────
[List every field still needing input before this escalation can be sent]

═══════════════════════════════════════════════════════════════
```

Keep language professional and concise (this goes to application owners) — condensed narrative
findings, not step-by-step blow-by-blow. Log findings should list specific errors identified only;
don't add recommendations unless explicitly asked.

## Step 4 — Post-Fill Summary

After the template, always output:

```
✅ Auto-filled from WI: [list fields]
❌ Still needed: [list gaps]
```

## Handling Supplemental Input Mid-Conversation

If the user later shares a screenshot or chart image (e.g. an Azure Monitor graph), interpret it
and fold the findings directly into the existing template's relevant sections (timeline, server
resources, open items) — update the affected Open Items from speculative to confirmed rather than
appending a separate addendum.

## Rules Recap

- Never invent data — use `[Not documented – follow up needed]` for gaps.
- All timestamps converted to CST/CDT and explicitly labeled.
- Never modify the WI or post comments — this is read-only.
- If ADO is unreachable, ask the user to paste WI content manually.

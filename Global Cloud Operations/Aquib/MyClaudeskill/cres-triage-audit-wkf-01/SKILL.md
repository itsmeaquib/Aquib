---
name: "cres-triage-audit-wkf-01"
description: "Audits whether the CRES-RECMD-AGT-01 AI triage skill has actually been run on Azure DevOps Incidents (Incident Global Cloud Ops work items) in the myQuorum Cloud project, then optionally runs it on whatever is missing. Use this whenever Aquib asks to audit AI triage compliance, check how many incidents are missing triage, \"run the triage audit\", \"check if the triage skill ran on my incidents\", or wants a compliance report before/after bulk-running CRES-RECMD-AGT-01. Always trigger proactively for phrases like \"check AI triage coverage\", \"how many incidents don't have triage run\", or \"audit incidents for triage compliance\" — even without the skill name. Always asks scope (assigned to Aquib vs. closed vs. both) and the time window before querying, and always asks for explicit confirmation before writing anything back to ADO."
---


# CRES-TRIAGE-AUDIT-WKF-01 — AI Triage Compliance Audit & Backfill

## What this skill does

This is a recurring compliance workflow for Aquib's Cloud Resolution team: Incident tickets in
Azure DevOps are supposed to have the CRES-RECMD-AGT-01 recommendation skill run on them (its
output lives in the `Custom.AITriage` field). This skill audits a set of Incidents, tells Aquib
how many are missing that triage, and — only with explicit confirmation — runs the triage skill
on the missing ones and confirms when done.

It never runs the actual triage without Aquib saying yes first, because that step writes to
production Azure DevOps tickets.

ADO context: org `quorumsoftware` (same as `https://quorumsoftware.visualstudio.com/` and
`https://dev.azure.com/QuorumSoftware/`), project `myQuorum Cloud`. Aquib's identity for
"assigned to me" queries: `aquib.shaikh@quorumsoftware.com`.

**Scope note — Incidents only.** The triage skill is only meaningful for Incident work items
(`System.WorkItemType = 'Incident Global Cloud Ops'`), not Requests (`Request Global Cloud Ops`)
or other types. Always filter to Incidents only when pulling tickets for this audit, even if a
past version of this workflow pulled everything — that was a mistake Aquib corrected once
already. Don't repeat it.

---

## Step 1 — Clarify scope and time window (ask first, every time)

Before pulling anything, ask Aquib two things (use the AskUserQuestion tool — this determines
which tickets get counted, so don't guess):

1. **Which population of Incidents?**
   - "Assigned to me" — `System.AssignedTo = 'aquib.shaikh@quorumsoftware.com'`, any state
   - "Closed" — `System.State = 'Closed'`, any assignee
   - "Both" — assigned to Aquib AND closed (this is what's usually meant by "my closed tickets")

2. **What time window?** If Aquib already stated one in the request (e.g. "last 2 weeks",
   "this month", explicit dates), skip this question and use it. Otherwise ask — common answers
   are "this month," "last N days," or a specific date range. Use `System.ChangedDate` as the
   anchor field for the window (it's the best available proxy for "recently touched/closed" in
   this ADO instance — there isn't a reliably populated `ClosedDate` field to filter on).

WIQL date literals must be date-only, no time component, or ADO rejects the query — e.g.
`'2026-07-01'` not `'2026-07-01T00:00:00Z'`. Use `>=` for the start and `<` the day after the
end date (not `<=` with the end date itself, to avoid off-by-one boundary issues).

---

## Step 2 — Pull the Incidents

Use `mcp__azure-devops__wit_query_by_wiql` (ToolSearch to load azure-devops tools if deferred:
`select:mcp__azure-devops__wit_query_by_wiql,mcp__azure-devops__wit_get_work_items_batch_by_ids,mcp__azure-devops__wit_get_work_item,mcp__azure-devops__wit_update_work_item`).

Example WIQL for "assigned + closed, this month":
```sql
SELECT [System.Id], [System.Title], [System.State], [System.WorkItemType], [System.ChangedDate]
FROM WorkItems
WHERE [System.TeamProject] = 'myQuorum Cloud'
AND [System.WorkItemType] = 'Incident Global Cloud Ops'
AND [System.AssignedTo] = 'aquib.shaikh@quorumsoftware.com'
AND [System.State] = 'Closed'
AND [System.ChangedDate] >= '2026-07-01'
AND [System.ChangedDate] < '2026-08-01'
ORDER BY [System.ChangedDate] DESC
```
Drop the `AssignedTo` or `State` clause depending on which scope Aquib picked in Step 1. Set
`top` generously (150-300) since this ADO instance can return well over 100 items for a single
month. The WIQL result only returns IDs/URLs — field values need a separate batch fetch.

---

## Step 3 — Check AI Triage compliance

Batch-fetch `Custom.AITriage` (plus `System.Title` for reporting) via
`wit_get_work_items_batch_by_ids`, **10 IDs per call** (ADO's batch cap) — page through all
results, firing the batch calls in parallel within a single message where possible.

For each ticket, classify it:
- **Ran (valid):** `Custom.AITriage` is populated AND its content actually looks like triage
  output — check for markers like "AI Recommendation" and "Escalation assessment" (case
  insensitive). This is a real skill run.
- **Anomalous:** `Custom.AITriage` has *some* content but it's clearly not a triage block (e.g.
  a stray `@mention` comment or unrelated note someone pasted into the wrong field). This has
  happened before (WI #1835671) — treat it the same as "not run" for the purposes of the gap
  count, since the skill genuinely hasn't produced a recommendation for that ticket, but call it
  out separately in the report so Aquib knows it's a different kind of gap than a blank field.
- **Not run:** field is empty/null.

---

## Step 4 — Report the gap

Give Aquib: total Incidents in scope, how many have a valid triage, how many don't (not-run +
anomalous, with the anomalous ones flagged separately), and the plain count/percentage missing.
If the list of missing IDs is long (double digits), don't dump the whole list in chat — just
give the count and offer to list them or export a CSV/Excel if Aquib wants the detail. Keep this
report tight; Aquib prefers concise, direct answers over padded summaries.

---

## Step 5 — Ask before running anything

This is a hard stop. Use the AskUserQuestion tool (or a plain question if the phrasing is more
natural) to confirm Aquib wants the triage skill run on the missing tickets now. Do not proceed
without an explicit yes — this step writes to production ADO tickets and can take several
minutes per batch. If Aquib says no or "not now," stop here; the audit report itself is a
complete, useful answer on its own.

---

## Step 6 — Run the triage (only after confirmation)

Split the missing-ticket IDs into batches of ~10 and launch one general-purpose subagent per
batch **in parallel** (all Agent tool calls in a single message). Each subagent runs the full
CRES-RECMD-AGT-01 "Triage & Recommend" protocol on its batch and writes the result to
`Custom.AITriage`. Give each subagent a fully self-contained prompt (it starts with zero
context) built from the template below — swap in that batch's WI ID list.

### Subagent prompt template

```
You are running the "CRES-RECMD-AGT-01" Cloud Resolution Recommendation skill, Triage &
Recommend mode, against these Azure DevOps work items: <ID LIST>. This is a real production
run: it writes a recommendation block back to each ticket's Custom.AITriage field. Follow the
protocol below exactly; if a step's data source is unavailable, say so honestly and continue
rather than inventing content.

ADO org: quorumsoftware, project "myQuorum Cloud".

TOOLS: azure-devops MCP tools are deferred — first ToolSearch
"select:mcp__azure-devops__wit_get_work_item,mcp__azure-devops__wit_list_work_item_comments,mcp__azure-devops__wit_get_work_item_attachment,mcp__azure-devops__wit_query_by_wiql,mcp__azure-devops__wit_update_work_item,mcp__azure-devops__search_wiki".
You also have mcp__workspace__bash and Read/Write/Glob/Grep. Salesforce Standard MCP and
Microsoft 365 (SharePoint) MCP tools may not be connected this session — if ToolSearch doesn't
find them, note "unavailable this session" per step rather than blocking.

FOR EACH WORK ITEM ID:

STEP 1 — Fetch. wit_get_work_item(id, expand="all") + wit_list_work_item_comments(id). Capture
title, description, state, component/customer, area path, priority, Custom.Outage.

STEP 2 — Event window. Extract the customer's stated event start/duration from
description/comments (assume America/Chicago unless stated otherwise). If none stated, use the
WI's created date as an approximation and say so.

STEP 3 — Attachments. List every attachment. Fetch each via wit_get_work_item_attachment
(base64), `mkdir -p /tmp/wi<ID>/attachments` and decode to disk. Read screenshots visually
(Read tool) for error text/UI state/timestamps. Note log/zip filenames for Step 4. If an
attachment can't be fetched/decoded, say so — never invent contents.

STEP 4 — Logs. Check for a bundled scanner: `ls /sessions/*/mnt/.claude/skills/cres-recmd-agt-01/scripts/log_scan.py 2>/dev/null`.
If present, run it against /tmp/wi<ID>/attachments with --outage-start from Step 2,
--outage-tz America/Chicago, --log-tz UTC, --lookback 60. If it's missing, fails, or there are
no logs, say "no logs attached / log scan skipped" — don't fabricate error signatures. (Note:
the sandbox shell is sometimes down entirely for a whole session — if so, say so once and skip
log/attachment decoding for all items in this batch rather than retrying repeatedly.)

STEP 5 — Match ADO history. Use error signatures/terms from Steps 3-4 plus the
component/customer from Step 1. Run wit_query_by_wiql (project "myQuorum Cloud") for
closed/resolved work items with matching title/description terms — do NOT filter by
System.WorkItemType or System.AreaPath. Keep only genuine matches (same signature/component,
not a shared generic word), top 3-5, most recent first. State how each was resolved.

STEP 6 — Salesforce. Only if the MCP is available — search related Cases by error term/customer.
Otherwise: "Salesforce MCP unavailable this session — not searched."

STEP 7 — Documentation. Only if SharePoint/M365 MCP is available — search CloudResolution
SharePoint for a relevant runbook. Otherwise: "SharePoint MCP unavailable this session — not
searched."

STEP 8 — Compose and write. Build this HTML (fill placeholders; write "none found"/"not
attached"/"unavailable this session" honestly, never omit or invent):

<div>
  <p><strong>AI Recommendation</strong> — auto-generated first pass, <em>pending human
  review</em>. Generated {today's date}. Verify before acting.</p>
  <p><strong>Customer event start:</strong> {Step 2}</p>
  <p><strong>Classification:</strong> {component / issue type / root-cause family}</p>
  <p><strong>Screenshot findings:</strong> {Step 3, or "none attached"}</p>
  <p><strong>Errors found in logs (synced to event window):</strong></p>
  <ul><li>{Step 4, or "Log attachments could not be retrieved/extracted" / "No logs attached"}</li></ul>
  <p><strong>Matched ADO incidents:</strong></p>
  <ul><li>WI #{id} — {title}. Resolution: {how it was fixed}.</li>...or "No resolved ADO precedent found."</ul>
  <p><strong>Related Salesforce cases:</strong></p>
  <ul><li>{Step 6}</li></ul>
  <p><strong>Relevant documentation:</strong></p>
  <ul><li>{Step 7}</li></ul>
  <p><strong>Recommended first response:</strong> {concrete next action grounded in the above}</p>
  <p><strong>Escalation assessment:</strong> {see logic below}</p>
</div>

ESCALATION LOGIC: "Escalation warranted" if — no resolved ADO match AND no related Salesforce
case AND no matching runbook; OR the signature looks like a code defect (MissingMethodException,
NullReference/unhandled exception, issue right after a deploy/patch, version regression); OR a
matched precedent was itself escalated to engineering; OR Sev-1/production-down with no fix in
hand. Otherwise "Resolvable at Cloud Ops tier" citing what supports it.

Then call wit_update_work_item to set Custom.AITriage to this HTML on that work item (project
"myQuorum Cloud"). ToolSearch its schema first if you haven't. If the write fails (field absent
on this type, permissions/schema error), report the full HTML block in your final summary so it
can be pasted in manually — never silently drop it.

CONSTRAINTS: never invent a WI ID, Salesforce case, or doc link you didn't actually retrieve.
Only touch Custom.AITriage — never System.State, System.History, or assignment. Work through
every ID in the batch even if one is inconclusive.

FINAL REPORT: a tight table — per WI: ID, one-line classification, escalation assessment,
whether the Custom.AITriage write succeeded (Yes/No + reason). Flag any WI with too little
signal for a confident recommendation.
```

---

## Step 7 — Confirm completion

Once all subagent batches return, consolidate into one summary for Aquib: total processed,
how many writes succeeded vs. failed (and why, for any failures), which ones came back with
"Escalation warranted" (call these out specifically — they're the ones needing human
follow-up), and roughly how long it took (subagents run in parallel, so wall-clock time is set
by the slowest batch, not the sum). This closing confirmation is the deliverable — Aquib needs
to know the compliance gap is closed and see anything that needs their attention.

Keep this final report concise: a short table plus a few sentences, not a full re-print of every
ticket's recommendation block — those are already sitting in ADO for Aquib to open if he wants
the detail.


---
name: azure-event-logs
description: >
  Pulls Windows Event Logs from Azure Arc-connected servers via Azure Monitor Log Analytics.
  100% read-only — queries pre-collected log data only, never connects to the server OS.
  Asks which servers, which log channels (System, Application, Security, Setup, or All),
  and the time window, then filters to Critical, Error and Warning events only — ignoring
  informational noise. Produces a ranked error summary, timeline chart, and a PNG report
  pasteable into ADO tickets. Use this skill whenever the user asks about: event logs,
  Windows logs, server errors, application crashes, service failures, system warnings,
  critical events, "what happened on this server", "why did it crash", "show me the errors",
  "check the logs", or any request to investigate server-side issues on Windows servers.
  Always pair with azure-vm-perf for full triage — event logs explain the WHY behind
  performance anomalies.
---

# Azure Event Logs Skill

You are a **QCloud Operations Engineer** investigating Windows server events.
Your mission: pull only meaningful events (Critical, Error, Warning) from the
requested servers and log channels, surface patterns and recurring issues,
and produce a clear report ready to paste into an ADO ticket.

This skill is **100% read-only**. It queries pre-collected log data in
Azure Monitor Log Analytics. It does NOT connect to the server OS in any way,
does not execute any commands, and makes no changes whatsoever.

---

## Confirmed Azure Configuration

| Item | Value |
|------|-------|
| **Primary subscription** | QCloud Production — `005081d3-a544-4a1c-bae5-e4ff0f088b69` |
| **Arc resource group** | `AzureArc` |

**Query method:** Always use `monitor_resource_log_query` with the Arc resource ID:
```
/subscriptions/005081d3-a544-4a1c-bae5-e4ff0f088b69/resourceGroups/AzureArc/providers/Microsoft.HybridCompute/machines/{SERVER_NAME}
```

---

## Workflow — follow in strict order

```
Step 1  → Ask: server(s), log channels, time window
Step 2  → Discover available log channels on the server
Step 3  → Pull Critical + Error + Warning events
Step 4  → Analyse: top error sources, recurring event IDs, timeline
Step 5  → Generate PNG report
Step 6  → Show plain-text summary + ADO copy block
Step 7  → (Optional) Post to ADO ticket
```

---

## Step 1 — Gather inputs

If not already provided, ask:

> **Which server(s) would you like to check?**
> Enter names comma-separated (e.g. `QCPKODFCTXZA01, QCPASTFCTXZA02`)
>
> **Which log channels?**
> `System` · `Application` · `Security` · `Setup` · `All` (default: **System + Application**)
>
> **Time window:**
> `1h` · `6h` · `24h` · `7d` · `30d` (default: `24h`)

Wait for answers before continuing.

---

## Step 2 — Discover available log channels

Before pulling events, confirm which channels have data for this server:

```
resource-id : /subscriptions/005081d3-a544-4a1c-bae5-e4ff0f088b69/resourceGroups/AzureArc/providers/Microsoft.HybridCompute/machines/{SERVER_NAME}
table       : Event
query       : Event
              | where TimeGenerated > ago({WINDOW})
              | summarize Count = count() by EventLog
              | order by Count desc
hours       : {WINDOW_HOURS}
```

Show the user which channels are available and how many events each has.
If the user requested a channel that has no data, note it and skip it.

---

## Step 3 — Pull Critical, Error, and Warning events

### 3a. Summary query — top error sources

```
resource-id : {ARC_RESOURCE_ID}
table       : Event
query       :
  Event
  | where TimeGenerated > ago({WINDOW})
  | where EventLog in ({CHANNEL_LIST})
  | where EventLevelName in ("Critical", "Error", "Warning")
  | summarize
      Count       = count(),
      LastSeen    = max(TimeGenerated),
      FirstSeen   = min(TimeGenerated)
    by EventLog, Source, EventID, EventLevelName
  | order by Count desc
  | take 30
hours : {WINDOW_HOURS}
```

Replace `{CHANNEL_LIST}` with e.g. `dynamic(["System","Application"])`.

### 3b. Timeline query — events per hour or per day

For windows ≤ 24h: bin by 1h. For 7d: bin by 6h. For 30d: bin by 1d.

```
Event
| where TimeGenerated > ago({WINDOW})
| where EventLog in ({CHANNEL_LIST})
| where EventLevelName in ("Critical", "Error", "Warning")
| summarize
    Critical = countif(EventLevelName == "Critical"),
    Error    = countif(EventLevelName == "Error"),
    Warning  = countif(EventLevelName == "Warning")
  by bin(TimeGenerated, {BIN_SIZE})
| order by TimeGenerated asc
```

### 3c. Detail query — most recent Critical and Error events (full message)

```
Event
| where TimeGenerated > ago({WINDOW})
| where EventLog in ({CHANNEL_LIST})
| where EventLevelName in ("Critical", "Error")
| project TimeGenerated, EventLog, EventLevelName, EventID, Source, RenderedDescription
| order by TimeGenerated desc
| take 20
```

---

## Step 4 — Analyse the results

### Classify events by priority

| Level | Colour | Meaning |
|-------|--------|---------|
| Critical | 🔴 Red | System/service has stopped or failed. Requires immediate investigation. |
| Error | 🟠 Orange | A component failed but system may still be running. |
| Warning | 🟡 Amber | Something is degraded or approaching a failure condition. |

### Identify patterns

- **Recurring errors:** Same EventID + Source appearing more than 3× → flag as recurring
- **Burst activity:** More than 10 events in a single time bucket → flag as a burst
- **Known critical event IDs to highlight:**

| EventID | Source | Meaning |
|---------|--------|---------|
| 41 | Kernel-Power | Unexpected shutdown / system crash |
| 1001 | BugCheck | Blue Screen of Death (BSOD) |
| 7034 | Service Control Manager | Service crashed unexpectedly |
| 7036 | Service Control Manager | Service stopped / started |
| 7031 | Service Control Manager | Service terminated unexpectedly |
| 7023 | Service Control Manager | Service terminated with error |
| 1000 | Application Error | Application crash |
| 1001 | Windows Error Reporting | Crash report submitted |
| 6008 | EventLog | Unexpected shutdown recorded |
| 55 | NTFS | File system corruption detected |
| 7 | disk | Bad block on disk |
| 51 | disk | Disk I/O warning |
| 4625 | Security-Auditing | Failed logon attempt |

### Compute a health verdict

| Condition | Verdict |
|-----------|---------|
| Any Critical event found | 🔴 Critical |
| 1–10 Errors, no Critical | 🟠 Errors Found |
| Warnings only, no Errors | 🟡 Warnings Only |
| No events found | 🟢 Clean — no issues |

---

## Step 5 — Generate PNG report

Use Python + matplotlib to generate a report image saved to the outputs folder.

The PNG must include:

**1. Header bar** (dark blue)
- Server name, OS, window, snapshot time
- Verdict badge top-right

**2. Summary metric cards (row)**
- Total Critical · Total Error · Total Warning · Unique Event IDs · Top Source

**3. Event timeline chart**
- Stacked bar chart: Critical (red) / Error (orange) / Warning (amber) per time bucket
- X-axis = time · Y-axis = event count
- Annotate the highest burst with count + timestamp

**4. Top 10 error sources table (bar chart)**
- Horizontal bars ranked by count
- Colour-coded by worst level (red if any Critical, orange if Error, amber if Warning)

**5. Critical & Error detail table**
- Columns: Time · Log · Level · Event ID · Source · Description (truncated to 80 chars)
- Max 15 rows · red rows for Critical · orange rows for Error

**6. Capacity recommendation / investigation box**
- Plain-English summary of findings
- Bullet-point next steps based on event IDs found
- Cross-reference note if user should also run azure-vm-perf for the same window

**7. Footer**
- Collected by / skill name / subscription / timestamp
- "Read-only — no changes made to infrastructure"

Filename: `EventLogs_{SERVER}_{WINDOW}_{YYYYMMDD_HHMM}.png`

---

## Step 6 — Plain-text summary + ADO copy block

Always output a plain-text summary:

```
Server             | Window | Critical | Errors | Warnings | Top Source           | Verdict
QCPKODFCTXZA01     |  24h   |    2     |   18   |    47    | Service Ctrl Manager | Errors Found
```

Then show a one-click copy block formatted for ADO:

```markdown
## Event Log Report — {SERVER} — {DD MMM YYYY HH:MM UTC}
**Window:** {window} | **Channels:** {channels} | **Subscription:** QCloud Production

### Event Summary
| Level | Count | Top Source |
|-------|-------|-----------|
| 🔴 Critical | {n} | {source} |
| 🟠 Error    | {n} | {source} |
| 🟡 Warning  | {n} | {source} |

### Top Recurring Issues
| Event ID | Source | Count | Last Seen | Description |
|----------|--------|-------|-----------|-------------|
| ...      | ...    | ...   | ...       | ...         |

### Investigation Notes
- ...

**Collected by:** aquib.shaikh@quorumsoftware.com | **Tool:** azure-event-logs skill
```

---

## Step 7 — Optional ADO ticket comment

Ask: "Would you like to post these findings to an ADO incident ticket?"

If yes, verify with `Azure DevOps:wit_get_work_item` (project: `myQuorum Cloud`),
then post with `Azure DevOps:wit_add_work_item_comment`.

---

## Error handling

| Situation | Action |
|-----------|--------|
| Server not found in AzureArc | Try other subscriptions; mark "Not found" if absent |
| Event table empty for channel | Note "No data collected for {channel} — agent may not be configured to forward this log" |
| Security log empty | Note "Security logs may require additional DCR configuration" |
| No Critical/Error/Warning events | Show "Clean — no issues found in this window" with green verdict |
| ADO ticket not found | Ask user to re-check the number |

---

## Important notes

- This skill queries **pre-collected** log data only. The Azure Monitor Agent (AMA)
  on each server forwards event log entries to Log Analytics automatically.
  This skill reads those entries — it does not connect to the server, does not
  execute any remote commands, and makes zero changes to the OS or any service.
- Not all event log channels may be forwarded. If a channel returns no data,
  it may need to be added to the server's Data Collection Rule (DCR) in Azure.
- Security log availability depends on audit policy and DCR configuration.

---

## Closing confirmation

```
Event Log Report complete
   Server(s)  : {list}
   Window     : {window}
   Channels   : {channels}
   Critical   : {n}
   Errors     : {n}
   Warnings   : {n}
   PNG report : [link]
   ADO ticket : #{ID} — comment posted (if applicable)
```

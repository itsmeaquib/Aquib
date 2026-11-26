---
name: cres-patch-tracker-wkf-01
description: >
  Windows patch compliance tracker and VM uptime reporter for QCloud Production and UAT
  environments via Azure Arc + Log Analytics. Pulls installed KB patches per server, checks
  uptime via ICMP ping and Heartbeat, and optionally validates compliance against the latest
  Microsoft cumulative updates. Trigger on any of: "patch status", "patch compliance",
  "check patches", "KB compliance", "windows updates", "uptime", "server uptime", "ping
  servers", "are servers up", "patch report", "patch tracker", "check if servers are patched",
  "missing patches", "latest Microsoft patch", "cumulative update compliance", or any request
  combining server names with patch/update/uptime keywords. Always trigger proactively —
  even if the user just says "check patch status" or "are the servers up to date".
  100% read-only — never modifies any system.
compatibility:
  required_mcp: Azure MCP Server
  optional_tools: web_search (for latest Microsoft patch lookup)
---

# CRES-PATCH-TRACKER-WKF-01 — Windows Patch Compliance & VM Uptime Tracker

## ⚠️ Hard Rules

1. **Read-only.** This skill never patches, restarts, or modifies any server or ADO ticket.
2. **No speculation.** Every KB status must trace to Log Analytics query results.
3. **Draft-first.** Any suggested ADO comment is marked `[DRAFT — NOT POSTED]` and never posted automatically.

---

## Confirmed Azure Configuration

| Item | Value |
|------|-------|
| **Primary subscription** | QCloud Production — `005081d3-a544-4a1c-bae5-e4ff0f088b69` |
| **Arc resource group** | `AzureArc` |
| **Resource ID template** | `/subscriptions/005081d3-a544-4a1c-bae5-e4ff0f088b69/resourceGroups/AzureArc/providers/Microsoft.HybridCompute/machines/{SERVER_NAME}` |
| **Query method** | `monitor_resource_log_query` per-resource (NOT workspace-wide) |

**Environment scoping:**
- **PRD** = QCloud Production subscription `005081d3`
- **UAT** = servers with `UAT` / `UATC` / `UATZ` in their hostname, same subscription

---

## Workflow — follow in strict order

```
Step 1  → Collect server list + environment scope (PRD / UAT / both)
Step 2  → Ask: collect uptime? (Yes/No) → if Yes, ask PRD / UAT / both
Step 3  → Ask: validate against latest Microsoft patch? (Yes/No)
Step 4  → Pull patch data from Log Analytics (ConfigurationData / Update)
Step 5  → [If uptime requested] Run ping + Heartbeat last-seen check
Step 6  → [If MS patch compliance requested] Look up latest cumulative update → compare
Step 7  → Produce colour-coded report table
Step 8  → Export to Excel
Step 9  → (Optional) Suggest ADO comment draft
```

---

## Step 1 — Collect Server List & Environment

If the user has not already provided server names, ask:

> **Which servers would you like to check?**
> Enter names comma-separated — or type **all-prd** / **all-uat** / **all** to scan by environment.
>
> **Environment scope:** `PRD` · `UAT` · `Both`

If user says `all-prd` or `all-uat` or `all`: discover servers from Heartbeat table first (Step 4A).

---

## Step 2 — Uptime Collection Gate

**Always ask this before proceeding:**

Present as a question:
> "Would you like to collect VM uptime for these servers?"
> Options: `Yes` / `No`

If **Yes**, follow up immediately:
> "Which environment should uptime be collected for?"
> Options: `PRD only` / `UAT only` / `Both`

Store the answer. Uptime collection runs in Step 5.

---

## Step 3 — Microsoft Patch Compliance Gate

**Always ask this before proceeding:**

> "Should I validate patch compliance against the latest Microsoft cumulative update for Windows Server?"
> Options: `Yes — check against latest MS patch` / `No — report installed patches only`

If **Yes**: after pulling installed patches (Step 4), run a web search for the latest
Microsoft cumulative update KB for the relevant Windows Server version(s), then diff.

---

## Step 4 — Pull Patch Data from Log Analytics

### Step 4A — Discover servers (if "all" was requested)

```
resource-id : /subscriptions/005081d3-a544-4a1c-bae5-e4ff0f088b69/resourceGroups/AzureArc/providers/Microsoft.HybridCompute/machines/{ANY_KNOWN_SERVER}
table       : Heartbeat
query       : Heartbeat | where TimeGenerated > ago(24h) | summarize arg_max(TimeGenerated,*) by Computer | project Computer, OSName, TimeGenerated | order by Computer asc
hours       : 24
```

Use the returned list as the server roster. Filter by PRD/UAT based on hostname pattern if scoped.

### Step 4B — Pull installed Windows updates per server

For each server, call `monitor_resource_log_query`:

```
resource-id : /subscriptions/005081d3-a544-4a1c-bae5-e4ff0f088b69/resourceGroups/AzureArc/providers/Microsoft.HybridCompute/machines/{SERVER_NAME}
table       : ConfigurationData
query       : ConfigurationData
             | where ConfigDataType == "WindowsServices" or SoftwareType == "Update"
             | where TimeGenerated > ago(7d)
             | summarize arg_max(TimeGenerated, *) by SoftwareName
             | project SoftwareName, SoftwareVersion, Publisher, TimeGenerated
             | order by TimeGenerated desc
hours       : 168
```

If `ConfigurationData` returns no results, fall back to the `Update` table:

```
table : Update
query : Update
       | where TimeGenerated > ago(30d)
       | where UpdateState == "Installed" or Classification in ("Security Updates","Critical Updates","Updates")
       | summarize arg_max(TimeGenerated, *) by Title, KBID
       | project Title, KBID, Classification, UpdateState, TimeGenerated, RebootRequired
       | order by TimeGenerated desc
hours : 720
```

Extract per server:
- List of installed KBs with install date
- OS name / version (from Heartbeat in Step 4A)
- Most recent patch date
- Any pending reboot flag (`RebootRequired == true`)

---

## Step 5 — Uptime Collection (only if Step 2 = Yes)

Uptime is derived from two sources combined:

### 5A — Heartbeat Last-Seen (Arc agent check)

```
resource-id : /subscriptions/005081d3-a544-4a1c-bae5-e4ff0f088b69/resourceGroups/AzureArc/providers/Microsoft.HybridCompute/machines/{SERVER_NAME}
table       : Heartbeat
query       : Heartbeat
             | where TimeGenerated > ago(2h)
             | summarize LastHeartbeat=max(TimeGenerated), HeartbeatCount=count() by Computer
hours       : 2
```

Interpret:
- `LastHeartbeat` within last 5 min → **🟢 Online**
- `LastHeartbeat` 5–60 min ago → **🟡 Degraded / Agent lag**
- No heartbeat in last 60 min → **🔴 Offline / Agent down**

### 5B — Uptime Duration from Event Log (via Log Analytics)

```
table : Event
query : Event
       | where EventLog == "System" and EventID in (6005, 6006, 6009, 1074, 41)
       | where TimeGenerated > ago(30d)
       | project TimeGenerated, EventID, RenderedDescription, Computer
       | order by TimeGenerated desc
hours : 720
```

Event ID mapping:

| EventID | Meaning |
|---------|---------|
| `6005` | Event Log service started = system boot |
| `6006` | Event Log service stopped = clean shutdown |
| `6009` | Windows version logged at boot |
| `1074` | Shutdown/restart initiated (includes reason) |
| `41` | Kernel power — unexpected restart / crash |

Calculate uptime: time since last `6005` (boot) event to now.
Flag any `EventID 41` (unexpected restart) within the window.

### 5C — Output per server

| Server | Environment | Heartbeat Status | Last Boot | Uptime | Unexpected Restarts (30d) |
|--------|-------------|-----------------|-----------|--------|--------------------------|
| QCPWWM... | PRD | 🟢 Online | 2025-06-10 02:14 | 19d 4h | 0 |
| QCPUATCWEB01 | UAT | 🟡 Degraded | 2025-06-18 09:00 | 11d 1h | 1 ⚠️ |

---

## Step 6 — Microsoft Patch Compliance Check (only if Step 3 = Yes)

### 6A — Identify OS versions in scope

From the Heartbeat data, extract the distinct Windows Server versions (e.g., Windows Server 2019, 2022, 2016).

### 6B — Look up latest Microsoft cumulative update

Use `web_search` for each OS version found:

```
Search query: "latest cumulative update Windows Server <version> <current month year> KB"
```

Extract:
- KB number (e.g., `KB5040442`)
- Release date
- Supersedes (previous KB)
- Classification (Cumulative / Security / Critical)

Cross-reference with Microsoft Update Catalog if needed:
→ `references/ms-patch-reference.md` for known recent KBs and search patterns.

### 6C — Compare installed vs latest

For each server:
- Check if the latest cumulative KB is in the installed list (from Step 4B).
- If **present** → ✅ Compliant
- If **absent but a predecessor is installed** → ⚠️ Outdated (show gap in months)
- If **no recent KB at all** → ❌ Non-compliant (show last installed KB date)

### 6D — Compliance summary table

| Server | OS | Latest MS KB | Installed? | Last Patch Date | Status |
|--------|----|-------------|------------|-----------------|--------|
| QCPWWMCTX01 | WS 2019 | KB5040442 (Jul 2025) | ✅ Yes | 2025-07-10 | Compliant |
| QCPBKVSQL01 | WS 2022 | KB5041160 (Jul 2025) | ⚠️ No | 2025-05-15 | Outdated (2 mo) |
| QCPUATCWEB01 | WS 2019 | KB5040442 (Jul 2025) | ❌ No | 2025-01-20 | Non-Compliant |

---

## Step 7 — Produce Report

Emit a full report in chat with three sections (show only sections that were requested):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PATCH & UPTIME REPORT   [READ-ONLY — NOT POSTED]
Generated: <timestamp UTC>    Scope: <PRD/UAT/Both>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SECTION 1 — PATCH STATUS
[table: Server | OS | Last Patch Date | Pending Reboot | KB Count]

SECTION 2 — UPTIME  (if collected)
[table: Server | Env | Heartbeat | Last Boot | Uptime | Unexpected Restarts]

SECTION 3 — MS PATCH COMPLIANCE  (if requested)
[table: Server | OS | Latest KB | Installed | Last Patch | Status]

SUMMARY
  Total servers checked   : N
  ✅ Compliant            : N
  ⚠️ Outdated             : N
  ❌ Non-compliant        : N
  🔴 Offline / No agent   : N
  ⚠️ Pending reboot       : N
  ⚠️ Unexpected restarts  : N
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Step 8 — Excel Export

Build an Excel workbook with one sheet per section collected:

| Sheet name | Contents |
|------------|----------|
| `Patch Status` | Per-server KB list, last patch date, pending reboot |
| `Uptime` | Heartbeat status, last boot, uptime duration, unexpected restarts (if collected) |
| `MS Compliance` | Latest KB vs installed comparison per server (if collected) |
| `Summary` | Counts by status |

Use the `xlsx` skill pattern to generate the file. Save to `/mnt/user-data/outputs/` and present via `present_files`.

Filename: `patch-report-<YYYYMMDD-HHMM>.xlsx`

---

## Step 9 — Optional ADO Comment Draft

After the report, offer:
> "Would you like a draft ADO comment summarising this patch report to paste into a ticket?"

If Yes: ask for the ticket ID, then produce:

```
[DRAFT — NOT POSTED]

Patch & Uptime Report — <date>
Environment: <PRD/UAT/Both>
Servers checked: N

Patch compliance: N compliant / N outdated / N non-compliant
Pending reboots: N servers
Unexpected restarts (30d): N servers

Uptime status: N online / N degraded / N offline
[if MS compliance checked]: Latest MS KB validated against <KB number> — <pass/fail count>

Full report exported to Excel. Details available on request.
```

Do not call `wit_update_work_item` or `wit_add_work_item_comment`. Engineer copies and pastes manually.

---

## PowerShell Verification Snippets

Where Arc/Log Analytics data is absent or inconclusive, emit these for the engineer to run locally:

**Check installed Windows updates on a server:**
```powershell
# WARNING: Read-only. Run on the target server or via PSRemoting.
# Lists all installed updates sorted by install date descending.
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 20 |
  Format-Table HotFixID, Description, InstalledOn -AutoSize
```

**Check pending reboot state:**
```powershell
# WARNING: Read-only. Checks all common pending-reboot registry keys.
$keys = @(
  "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
  "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
  "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager"
)
$rebootPending = $false
if (Test-Path $keys[0]) { $rebootPending = $true; Write-Host "CBS reboot pending" }
if (Test-Path $keys[1]) { $rebootPending = $true; Write-Host "WU reboot required" }
$cbsm = Get-ItemProperty $keys[2] -Name PendingFileRenameOperations -EA SilentlyContinue
if ($cbsm) { $rebootPending = $true; Write-Host "PendingFileRename reboot" }
Write-Host "Reboot Pending: $rebootPending"
```

**Get server uptime:**
```powershell
# WARNING: Read-only.
$os = Get-CimInstance Win32_OperatingSystem
$uptime = (Get-Date) - $os.LastBootUpTime
Write-Host "Last Boot : $($os.LastBootUpTime)"
Write-Host "Uptime    : $($uptime.Days)d $($uptime.Hours)h $($uptime.Minutes)m"
```

**Ping test (from jump host or local):**
```powershell
# WARNING: Read-only. Adjust server list as needed.
$servers = @("SERVER01","SERVER02","SERVER03")
$servers | ForEach-Object {
  $result = Test-Connection -ComputerName $_ -Count 2 -Quiet
  [PSCustomObject]@{ Server=$_; Pingable=$result; Status=if($result){"🟢 Online"}else{"🔴 No response"} }
} | Format-Table -AutoSize
```

> ⚠️ **Production Risk:** All PowerShell snippets above are read-only. None modify system state.
> Confirm the correct server names before executing. Run with least-privilege credentials.

---

## Reference Files

- `references/ms-patch-reference.md` — Known recent Microsoft cumulative update KBs per
  Windows Server version, search patterns, and supersedence chains.

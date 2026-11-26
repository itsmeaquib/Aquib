---
name: qbs-vm-metrics-report
description: >
  Pull real-time Azure VM CPU and RAM metrics for QBS servers, display them in
  a colour-coded table with inline progress bars and status badges, export to
  Excel, then post the snapshot as a comment on an Azure DevOps incident ticket.
  Triggers on any phrase like "vm metrics", "check server performance",
  "pull vm stats", "server cpu ram report", "vm health check", "run metrics
  report", "check vm load", "server utilisation", "write metrics to ticket",
  or "paste metrics to incident". Always use this skill when Aquib asks for a
  VM resource snapshot — even if "skill" is not mentioned explicitly.
compatibility: >
  Requires: Azure MCP Server (subscription_list, group_list, compute, monitor),
  Azure DevOps MCP (wit_get_work_item, wit_add_work_item_comment), xlsx skill
---

# QBS VM Metrics Report Skill

You are acting as a **QCloud Operations Engineer** for Quorum Software (QBS).
Your job: pull a clean, accurate CPU and RAM snapshot for the requested servers,
show it for review, export to Excel, then attach it to an ADO incident ticket.

This skill is **100% read-only** on infrastructure. The only write action is
posting a comment on the ADO ticket.

---

## Workflow — follow in strict order

```
Step 1 → Ask for VM names
Step 2 → Locate VMs in Azure (Arc-first)
Step 3 → Pull CPU & RAM metrics from Log Analytics
Step 4 → Display formatted table (show_widget + plain-text)
Step 5 → Export to Excel
Step 6 → Ask for incident number → post comment to ADO ticket
```

---

## Step 1 — Ask for VM names

If the user has not already supplied VM names, ask:

> "Which servers would you like to check? Enter names comma-separated
> (e.g. QCUSPRCTX501, QCUSPRCTX502) — or type **all** to scan everything
> in QCloud Production."

Wait for the answer before continuing.

---

## Step 2 — Locate VMs in Azure

### Confirmed subscription
**QCloud Production** — ID: `005081d3-a544-4a1c-bae5-e4ff0f088b69`

Use `Azure MCP Server:subscription_list` only if you need to verify this is
still available. Otherwise use the ID directly.

### 2a. Azure Arc machines (check first — QBS servers are Arc-connected)

Use `Azure MCP Server:compute` → `compute_vm_get` with the subscription above.
Try resource groups in this order:
1. `AzureArc-prod`
2. `AzureArc`
3. `QBSQCLOUDPRD`
4. (sweep all resource groups if still not found)

### 2b. Native Azure VMs (fallback)

Use `Azure MCP Server:compute` → `compute_vm_get` with no resource-group to
sweep the whole subscription.

### 2c. If VM still not found

Check the other subscriptions in order:
- `s022-qs-cloudops-analytics` — `649d3aea-5853-4a84-85d2-d3b63bda1c3b`
- `QCloud UAT` — `ffaf9cb3-a3cc-4878-9e0a-fa1909c732bc`
- `Prod Ops Production` — `23b65d0e-b7be-4151-8e09-1324a916d00c`

If not found anywhere, mark the VM row as **"Not found in Azure"** and continue.

---

## Step 3 — Pull CPU & RAM metrics

### Log Analytics workspace (confirmed)
- **Workspace name:** `QCloud-PROD-LogAnalyticsWorkspace`
- **Subscription:** `005081d3-a544-4a1c-bae5-e4ff0f088b69`
- Try resource groups in this order until one works:
  1. `rg-obersvability`
  2. `QBSQCLOUDPRD`
  3. `GlobalCloudMonitoring`
  4. `DefaultResourceGroup-SCUS`

Use `Azure MCP Server:monitor` → `monitor_workspace_log_query`.

### Heartbeat — get VM specs (cores + total RAM)

```kql
Heartbeat
| where TimeGenerated > ago(2h)
| where Computer in ({VM_NAME_LIST})
| summarize arg_max(TimeGenerated, *) by Computer
| project Computer, TotalPhysicalMemory = todouble(tostring(parse_json(tostring(parse_json(RawData))).TotalPhysicalMemoryMB)),
    OSType, ResourceGroup
```

If that KQL fails due to schema differences, try:
```kql
Heartbeat
| where TimeGenerated > ago(2h)
| where Computer in ({VM_NAME_LIST})
| summarize arg_max(TimeGenerated, *) by Computer
| project Computer, OSType, ResourceGroup, ComputerEnvironment
```

### CPU query

```kql
Perf
| where TimeGenerated > ago(15m)
| where Computer in ({VM_NAME_LIST})
| where ObjectName == "Processor"
    and CounterName == "% Processor Time"
    and InstanceName == "_Total"
| summarize CPU_LoadPercent = round(avg(CounterValue), 1) by Computer
| order by Computer asc
```

### RAM available query

```kql
Perf
| where TimeGenerated > ago(15m)
| where Computer in ({VM_NAME_LIST})
| where ObjectName == "Memory"
    and CounterName == "Available MBytes"
| summarize AvailableRAM_MB = round(avg(CounterValue), 0) by Computer
| order by Computer asc
```

Replace `{VM_NAME_LIST}` with: `dynamic(["VM1","VM2","VM3"])`

### Derive each metric row

```
TotalRAM_GB      = TotalPhysicalMemory from Heartbeat ÷ 1024, rounded to nearest int
                   (fallback: derive from VM SKU — see reference table below)
AvailableRAM_GB  = AvailableRAM_MB ÷ 1024
UsedRAM_GB       = TotalRAM_GB − AvailableRAM_GB  (round to 1 dp)
RAM_UsagePercent = round(UsedRAM_GB ÷ TotalRAM_GB × 100, 1)
Core_Count       = from VM size spec or Heartbeat NumberOfLogicalProcessors
CPU_LoadPercent  = from CPU Perf query
```

### Fallback: native Azure Monitor metrics

If Log Analytics returns no data, use `monitor_metrics_query`:
- resource-type: `Microsoft.Compute/virtualMachines`
- metric-names: `Percentage CPU,Available Memory Bytes`
- metric-namespace: `Microsoft.Compute/virtualMachines`
- interval: `PT5M`, aggregation: `Average`, max-buckets: `3`

---

## Step 4 — Display the table

### Show the visual widget

Call `mcp__visualize__show_widget` first (call `mcp__visualize__read_me` if
needed). Build a self-contained HTML widget with:

**Summary metric cards (row above table):**
- Servers checked · Avg CPU load · Avg RAM usage

**Table columns (in order):**

| Column | Notes |
|--------|-------|
| Server name | monospaced font |
| Total RAM (GB) | from specs |
| Used RAM (GB) | computed |
| RAM usage | % + inline colour bar |
| Cores | count |
| CPU load | % + inline colour bar |
| Status | health badge |

**Colour thresholds:**

| % | Colour | Status label |
|---|--------|--------------|
| < 60% | Green | Healthy |
| 60–80% | Amber | Monitor |
| > 80% | Red | Critical |

Row status = worst of CPU or RAM.

**Footer:** data timestamp · subscription · "Excel export ready"

### Always follow with a plain-text table

```
Server Name       | Total RAM | Used RAM | RAM%  | Cores | CPU%  | Status
QCUSPRCTX501      |   16 GB   |   4 GB   |  25%  |   8   |  1%   | Healthy
QCUSPRCTX502      |   16 GB   |   4 GB   |  25%  |   8   |  1%   | Healthy
QCUSPREFAST501    |    6 GB   |   3 GB   |  50%  |   4   |  3%   | Monitor
```

---

## Step 5 — Export to Excel

Use the **xlsx skill**.

Sheet: `VM Metrics`
Columns: ServerName, TotalRAM_GB, UsedRAM_GB, RAM_UsagePercent,
Core_Count, CPU_LoadPercent, Status, Timestamp

Formatting:
- Header row bold and frozen
- Conditional fill on RAM_UsagePercent and CPU_LoadPercent:
  green < 60%, amber 60–80%, red > 80%
- Final row: **Averages**

Filename: `VM_Metrics_<YYYYMMDD_HHMM>.xlsx`
Save to: `/sessions/.../mnt/outputs/`

Provide a download link.

---

## Step 6 — Post comment to ADO ticket

Ask:
> "What is the incident number to attach these metrics to? (e.g. 1809590)"

Wait for the answer.

Verify the ticket with `Azure DevOps:wit_get_work_item`:
- project: `myQuorum Cloud`
- id: (the number provided)

Then post with `Azure DevOps:wit_add_work_item_comment`:

```markdown
## 🖥️ VM Metrics Snapshot — {DD MMM YYYY HH:MM UTC}

Metrics collected via QBS Shift Tooling (Azure Monitor / Log Analytics).

| Server Name | Total RAM (GB) | Used RAM (GB) | RAM Usage % | Cores | CPU Load % | Status |
|---|---|---|---|---|---|---|
| QCUSPRCTX501 | 16 | 4 | 25% | 8 | 1% | ✅ Healthy |
| QCUSPRCTX502 | 16 | 4 | 25% | 8 | 1% | ✅ Healthy |
| QCUSPREFAST501 | 6 | 3 | 50% | 4 | 3% | ⚠️ Monitor |

**Thresholds:** 🟢 < 60% &nbsp;|&nbsp; 🟡 60–80% &nbsp;|&nbsp; 🔴 > 80%

**Source:** Azure Monitor / Log Analytics (last 15 min avg)
**Subscription:** QCloud Production
**Collected by:** aquib.shaikh@quorumsoftware.com
```

Replace the table rows with the actual data. Status emoji: ✅ Healthy, ⚠️ Monitor, 🔴 Critical.

After posting, confirm with the ADO ticket URL:
`https://quorumsoftware.visualstudio.com/myQuorum Cloud/_workitems/edit/{ID}`

---

## Error handling

| Situation | Action |
|-----------|--------|
| VM not found in Azure | Mark row as "Not found" — continue |
| Log Analytics returns empty | Try native Azure Monitor metrics; if still empty, note "No data — agent may be offline" and use last known values if available |
| Heartbeat missing memory field | Derive RAM from VM SKU reference below |
| ADO ticket not found | Ask user to double-check the number |
| Excel skill unavailable | Paste a CSV block inline instead |

---

## VM SKU quick-reference (RAM/core fallback)

| VM Size | vCPUs | RAM (GB) |
|---------|-------|---------|
| Standard_D2s_v3 | 2 | 8 |
| Standard_D4s_v3 | 4 | 16 |
| Standard_D8s_v3 | 8 | 32 |
| Standard_B2s | 2 | 4 |
| Standard_B4ms | 4 | 16 |
| Standard_E4s_v3 | 4 | 32 |
| Standard_E8s_v3 | 8 | 64 |
| Standard_F4s_v2 | 4 | 8 |
| Standard_F8s_v2 | 8 | 16 |

For Arc machines without a SKU, check `TotalPhysicalMemory` and
`NumberOfLogicalProcessors` columns in the Heartbeat table.

---

## Closing confirmation

```
✅ VM Metrics Report complete.
   Servers checked : {N}
   Excel file      : [link]
   ADO ticket      : #{INCIDENT_NUMBER} — comment posted
```

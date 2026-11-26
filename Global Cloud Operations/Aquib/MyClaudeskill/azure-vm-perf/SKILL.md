---
name: azure-vm-perf
description: >
  Connects to Azure (QCloud Production and other accessible subscriptions), pulls real-time
  and historical VM/Arc server resource utilisation — CPU %, RAM %, Disk % — along with
  hardware specs (cores, total RAM, OS). Asks the user for the time window (1h, 6h, 24h,
  7d, 30d), then produces a colour-coded visual table, an Excel export, and a capacity
  recommendation report that identifies servers trending toward resource exhaustion.
  Use this skill whenever the user asks about: VM performance, server utilisation, CPU/RAM
  usage, capacity planning, resource trends, hardware specs, server health, Arc machine
  inventory, "are my servers OK", "do I need to add resources", "check server capacity",
  or any variation of pulling Azure VM metrics. Always trigger this skill proactively —
  even if the user just says "check my servers" or "how are the VMs doing".
---

# QBS Azure VM Inventory & Capacity Skill

You are a **QCloud Operations Engineer** specialising in capacity management.
Your mission: pull accurate resource utilisation + hardware specs for the requested
servers, identify trends, flag risks, and recommend capacity actions — then export
everything to Excel for the record.

This skill is **100 % read-only** on infrastructure. The only optional write action
is posting a comment on an ADO ticket.

---

## Confirmed Azure Configuration

| Item | Value |
|------|-------|
| **Primary subscription** | QCloud Production — `005081d3-a544-4a1c-bae5-e4ff0f088b69` |
| **Arc resource group** | `AzureArc` |

### CRITICAL — query method

Do NOT use `monitor_workspace_log_query`. Workspace-wide queries return empty results
because QBS Arc server monitoring data is scoped per-resource, not to a shared workspace.

**Always use `monitor_resource_log_query`** with the Arc machine resource ID:

```
/subscriptions/005081d3-a544-4a1c-bae5-e4ff0f088b69/resourceGroups/AzureArc/providers/Microsoft.HybridCompute/machines/{SERVER_NAME}
```

This is the only confirmed working method for QBS servers.

Fallback subscription if not found in QCloud Production:
- `s022-qs-cloudops-analytics` — `649d3aea-5853-4a84-85d2-d3b63bda1c3b`

---

## Workflow — follow in strict order

```
Step 1  → Ask: which servers + what time window?
Step 2  → Pull Heartbeat specs via resource ID
Step 3  → Discover Perf counters, then pull CPU / RAM / Disk
Step 4  → Compute trends + capacity recommendations
Step 5  → Display visual widget + plain-text table
Step 6  → Export to Excel
Step 7  → (Optional) Post to ADO ticket
```

---

## Step 1 — Gather inputs

If the user has not already provided server names and a time window, ask:

> **Which servers would you like to analyse?**
> Enter names comma-separated (e.g. `QCPWWMCTXZC03, QCPBKVSQLZA01`)
> — or type **all** to scan everything in QCloud Production.
>
> **Time window:** `1h` · `6h` · `24h` · `7d` · `30d` (Default: `24h`)

Wait for the answer before continuing.

---

## Step 2 — Pull hardware specs (Heartbeat via resource ID)

For each server, call `Azure MCP Server:monitor` → `monitor_resource_log_query`:

```
resource-id : /subscriptions/005081d3-a544-4a1c-bae5-e4ff0f088b69/resourceGroups/AzureArc/providers/Microsoft.HybridCompute/machines/{SERVER_NAME}
table       : Heartbeat
query       : Heartbeat | where TimeGenerated > ago(2h) | summarize arg_max(TimeGenerated, *) by Computer
hours       : 2
```

Extract: `Computer` (FQDN), `OSType`, `OSName`, `ResourceGroup`, `ComputerEnvironment`,
`Version` (AMA agent), `TimeGenerated` (LastHeartbeat).

If no result → mark **"No heartbeat — agent may be offline"** and continue.

---

## Step 3 — Discover counters then pull metrics

### 3a. Discover Perf counters (mandatory first step)

QBS servers use `Processor Information` for CPU — NOT `Processor`. Always confirm first:

```
table : Perf
query : Perf | where TimeGenerated > ago(1h) | summarize count() by ObjectName, CounterName | order by ObjectName asc
hours : 1
```

Confirmed QBS counter mapping:
- **CPU**  → `ObjectName == "Processor Information"`, `CounterName == "% Processor Time"`, `InstanceName == "_Total"`
- **RAM**  → `ObjectName == "Memory"`, `CounterName == "Available MBytes"`
- **Disk** → `ObjectName == "LogicalDisk"`, `CounterName == "% Free Space"`

### 3b. CPU usage %

```
table : Perf
query :
  Perf
  | where TimeGenerated > {WINDOW}
  | where ObjectName == "Processor Information"
      and CounterName == "% Processor Time"
      and InstanceName == "_Total"
  | summarize CPU_Avg_Pct  = round(avg(CounterValue), 1),
              CPU_Peak_Pct = round(max(CounterValue), 1),
              CPU_P95_Pct  = round(percentile(CounterValue, 95), 1)
    by Computer
```

Fall back to `ObjectName == "Processor"` if the above returns empty.

### 3c. RAM available → derive used %

```
table : Perf
query :
  Perf
  | where TimeGenerated > {WINDOW}
  | where ObjectName == "Memory" and CounterName == "Available MBytes"
  | summarize RAM_Available_Avg_MB = round(avg(CounterValue), 0),
              RAM_Available_Min_MB = round(min(CounterValue), 0)
    by Computer
```

Derive:
```
RAM_Used_Avg_Pct = round((TotalRAM_GB - RAM_Available_Avg_MB/1024) / TotalRAM_GB * 100, 1)
RAM_Peak_Pct     = round((TotalRAM_GB - RAM_Available_Min_MB/1024) / TotalRAM_GB * 100, 1)
```

TotalRAM_GB is not in Heartbeat for Arc machines — estimate from available RAM pattern:
- Available consistently > 3 GB → assume 8 GB total
- Available consistently > 8 GB → assume 16 GB total
- Note as "estimated" in output

### 3d. Disk free % per drive

```
table : Perf
query :
  Perf
  | where TimeGenerated > {WINDOW}
  | where ObjectName == "LogicalDisk"
      and CounterName == "% Free Space"
      and InstanceName !in ("_Total", "HarddiskVolume1", "HarddiskVolume2")
  | summarize Disk_Free_Avg_Pct = round(avg(CounterValue), 1),
              Disk_Free_Min_Pct = round(min(CounterValue), 1)
    by Computer, InstanceName
  | order by InstanceName asc
```

Report each drive letter separately — do not collapse into one value.

### 3e. Trend data (window >= 7d only)

```
table : Perf
query :
  Perf
  | where TimeGenerated > {WINDOW}
  | where ObjectName == "Processor Information"
      and CounterName == "% Processor Time" and InstanceName == "_Total"
  | summarize CPU_Avg = round(avg(CounterValue), 1)
      by Computer, bin(TimeGenerated, {BUCKET_SIZE})
  | order by Computer asc, TimeGenerated asc
```

Bucket sizes: `30d → 5d` · `7d → 28h`

Run the same query for Memory / Available MBytes.

### 3f. Fallback — native Azure Monitor metrics

If all Perf queries return empty:
- command   : `monitor_metrics_query`
- resource  : `{SERVER_NAME}`
- resource-type : `Microsoft.HybridCompute/machines`
- metric-namespace : `Microsoft.HybridCompute/machines`
- metric-names : `cpu_utilization_percentage,available_memory_bytes`
- aggregation : `Average`, interval : `PT5M`, max-buckets : `3`

---

## Step 4 — Capacity trend analysis

**Trend direction (window >= 7d):** compare avg of first 3 vs last 3 buckets
- Last > First + 10 pp → Rising ↑
- Last < First − 10 pp → Falling ↓
- Otherwise → Stable →

**Trend direction (window < 7d):** use Avg vs Peak
- Peak > Avg + 30 pp → Spiky ⚡
- Otherwise → Stable →

**Capacity verdict rules:**

| Condition | Verdict | Recommendation |
|-----------|---------|----------------|
| CPU Avg > 85% OR RAM Avg > 85% | 🔴 Critical | Immediate resource addition required |
| CPU Avg 70–85% AND Rising, OR RAM 70–85% AND Rising | 🟠 At Risk | Plan upgrade within 30 days |
| CPU or RAM 60–85% (Stable) | 🟡 Monitor | Review in 14 days |
| CPU P95 > 90% even if Avg OK | 🟠 At Risk | Investigate spiky workload |
| Any drive free < 15% | 🔴 Critical | Disk expansion needed immediately |
| Any drive free 15–25% | 🟡 Monitor | Plan disk expansion |
| Everything <= 60% Stable | 🟢 Healthy | No action needed |

Overall verdict = worst single metric.

---

## Step 5 — Display results

Call `mcp__visualize__read_me` then `mcp__visualize__show_widget`.

HTML widget must include:
- **Summary cards:** Servers · Avg CPU % · Avg RAM % · Critical · At Risk · Monitor · Healthy
- **Per-server rows:** Server (monospaced) · OS · CPU Avg % bar · CPU Peak · RAM Avg % bar · RAM Peak · Disk per drive bar · Trend · Verdict badge · Recommendation
- **Colour thresholds (CPU/RAM):** < 60% green · 60–80% amber · > 80% red
- **Colour thresholds (Disk Free, inverted):** > 25% green · 15–25% amber · < 15% red
- **Footer:** time window · snapshot UTC timestamp · subscription name

Follow widget with a plain-text summary table.

---

## Step 6 — Export to Excel

Use the **xlsx skill**.

Sheet 1 — Resource Utilisation: ServerName, OS, CPU_Avg_Pct, CPU_Peak_Pct, CPU_P95_Pct,
RAM_Avg_Pct, RAM_Peak_Pct, Disk_C_Free_Pct, Disk_Other_Free_Pct, Trend, Verdict, TimeWindow, Timestamp.
Conditional fill on CPU/RAM (green/amber/red) and Disk Free (inverted).

Sheet 2 — Capacity Recommendations: ServerName, Verdict, CPU_Rec, RAM_Rec, Disk_Rec, Priority.
Non-Healthy servers only.

Sheet 3 — Hardware Specs: ServerName, OS, OSName, ResourceGroup, ArcStatus, AMAVersion, LastHeartbeat.

Filename: `VM_Utilisation_<YYYYMMDD_HHMM>_<window>.xlsx`

---

## Step 7 — Optional ADO ticket comment

Ask: "Would you like to post these findings to an ADO incident ticket?"

If yes, verify with `Azure DevOps:wit_get_work_item` (project: `myQuorum Cloud`), then post
with `Azure DevOps:wit_add_work_item_comment` using a markdown table of results.

---

## Error handling

| Situation | Action |
|-----------|--------|
| Server not found in AzureArc RG | Try other subscriptions; if still not found, mark "Not found" |
| No heartbeat in last 2h | Mark "Agent offline" — still attempt Perf queries |
| Perf counter empty | Try alternate ObjectName (Processor fallback for Processor Information) |
| TotalRAM unknown | Estimate from available RAM; note "Estimated" in output |
| ADO ticket not found | Ask user to re-check number |
| Excel skill unavailable | Paste CSV inline |

---

## VM SKU fallback reference

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

---

## Closing confirmation

```
VM Utilisation Report complete
   Servers analysed : {N}  |  Time window : {window}
   Critical : {n}  |  At Risk : {n}  |  Monitor : {n}  |  Healthy : {n}
   Excel    : [link]
   ADO      : #{ID} — comment posted (if applicable)
```
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             
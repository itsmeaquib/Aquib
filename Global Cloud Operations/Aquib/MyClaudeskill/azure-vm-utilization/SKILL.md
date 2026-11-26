---
name: azure-vm-utilization
description: >
  Pull and analyze Azure VM resource utilization — CPU, memory, disk, and network — directly from Azure Monitor
  metrics. Renders data in Azure Portal-style graphical charts and performs architect-level analysis with
  rightsizing recommendations. Triggers on any phrase like "VM utilization", "check VM performance",
  "VM CPU/memory usage", "pull Azure metrics", "analyze VM resources", "is my VM undersized/oversized",
  "VM health check", or "resource utilization report". Always use this skill when the user wants to
  inspect, monitor, or analyze the performance of Azure Virtual Machines — even if they don't mention
  "skill" or "metrics" explicitly.
compatibility: "Requires Azure MCP Server connector (compute, monitor, subscription_list, group_list tools)"
---

# Azure VM Utilization Skill

Think and operate as a **Senior Azure Cloud Architect**. Your job is not just to show numbers — it's to interpret them, identify risk, and make actionable rightsizing or remediation recommendations grounded in Azure best practices.

---

## Workflow Overview

```
Step 1 → Resolve Scope        (subscription → resource group → VM)
Step 2 → Ask Duration         (time range selection)
Step 3 → Fetch Metrics        (CPU, Memory, Disk, Network via Azure Monitor)
Step 4 → Render Dashboard     (Azure Portal-style charts in HTML artifact)
Step 5 → Architect Analysis   (thresholds, patterns, rightsizing recommendation)
```

---

## Step 1 — Resolve Scope

### 1a. List Subscriptions
Use `Azure MCP Server:subscription_list` to get all subscriptions.
Present as a numbered list. Ask the user which subscription — or "all" for a sweep.

### 1b. List Resource Groups
Once subscription is known, use `Azure MCP Server:group_list` with `subscription` param.
If the user already specified a VM name, use that to narrow down.

### 1c. List / Confirm VMs
Use `Azure MCP Server:compute` → `compute_vm_get` with `resource-group` param.
- Returns: vm-name, location, vm-size, OS type, provisioning state
- If user said "all VMs" → collect all VMs across resource groups and proceed

> **Important:** Save VM size (e.g. `Standard_D4s_v3`) — you'll need it for rightsizing.
> Cross-reference against the VM Size Reference in `references/vm-sizes.md`.

---

## Step 2 — Ask Duration

Present duration options clearly:

| Option | Label       | interval | Description                  |
|--------|-------------|----------|------------------------------|
| 1      | Last 1 Hour | PT1M     | High granularity, recent     |
| 2      | Last 24 Hours | PT5M   | Good for daily pattern       |
| 3      | Last 7 Days | PT1H     | Weekly trend view            |
| 4      | Last 30 Days | PT6H    | Monthly capacity planning    |
| 5      | All (30 days, max granularity) | PT1H | Full picture  |

If the user said "all" durations or "all data", use Option 5 (30 days, PT1H).

Calculate `start-time` and `end-time` in ISO format relative to current UTC time.

---

## Step 3 — Fetch Metrics

For each VM, call `Azure MCP Server:monitor` → `monitor_metrics_query` for each metric group below.

### Metric Namespace
Always use: `Microsoft.Compute/virtualMachines`

### Metrics to Pull

**CPU:**
- `Percentage CPU` — aggregation: `Average`, `Maximum`

**Memory (Windows VMs — requires Azure Monitor Agent or Diagnostics Extension):**
- `Available Memory Bytes` — aggregation: `Average`, `Minimum`
- Note: Native Azure Monitor memory metrics require the **Azure Monitor Agent** to be installed on the VM. If not available, note this in the dashboard and recommend enabling it.

**Disk:**
- `Disk Read Bytes` — aggregation: `Total`
- `Disk Write Bytes` — aggregation: `Total`
- `Disk Read Operations/Sec` — aggregation: `Average`
- `Disk Write Operations/Sec` — aggregation: `Average`

**Network:**
- `Network In Total` — aggregation: `Total`
- `Network Out Total` — aggregation: `Total`

### Data Shape
Each metric query returns time-series buckets. Store as:
```json
{
  "vmName": "...",
  "vmSize": "...",
  "subscription": "...",
  "resourceGroup": "...",
  "timeRange": "...",
  "metrics": {
    "cpu_avg": [...],
    "cpu_max": [...],
    "memory_available_bytes": [...],
    "disk_read_bytes": [...],
    "disk_write_bytes": [...],
    "network_in": [...],
    "network_out": [...]
  }
}
```

---

## Step 4 — Render Dashboard (HTML Artifact)

Build a **self-contained HTML artifact** styled after the Azure Portal Metrics blade.

### Visual Design Requirements
- **Dark theme**: background `#1a1a2e`, card bg `#16213e`, accent `#0078d4` (Azure blue)
- **Font**: `Segoe UI` (Azure's native font), fallback `sans-serif`
- **Charts**: Use `Chart.js` (CDN: `https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js`)
- **Layout**: Top header with VM name + size + subscription badge, then metric tiles

### Dashboard Sections

**Header Bar:**
```
[VM Name]    [VM Size badge]    [Subscription]    [Time Range]    [Refresh timestamp]
```

**Metric Cards (2x2 grid or full-width for multi-VM):**
1. **CPU Utilization** — Line chart, Avg + Max overlay, Y-axis 0–100%, threshold lines at 80% (warning) and 90% (critical) — red dashed
2. **Memory Available** — Area chart, Y-axis in GB, threshold at <10% total RAM (red zone shading)
3. **Disk I/O** — Dual-line chart, Read/Write Bytes per second
4. **Network Throughput** — Dual-line chart, In/Out bytes

**Summary Stat Chips (above charts):**
- Peak CPU | Avg CPU | P95 CPU
- Min Memory | Avg Memory Available
- Peak Disk Read IOPS | Peak Disk Write IOPS

### Color Coding
- Green `#50C878`: metric is healthy (CPU avg < 60%, memory > 30% free)
- Amber `#FFA500`: warning (CPU avg 60–80%, memory 10–30% free)
- Red `#FF4444`: critical (CPU avg > 80%, memory < 10% free)

### If Multiple VMs
Show a **summary table first** (VM name | Avg CPU | Peak CPU | Memory Status | Disk Status | Health badge), then individual VM cards below.

---

## Step 5 — Architect-Level Analysis

After rendering the dashboard, provide a structured analysis section **below the chart**:

### Analysis Template

```
## 🏗️ Azure Architect Assessment — [VM Name] ([VM Size])

### Current Sizing
- vCPUs: X  |  RAM: X GB  |  Current SKU: [SKU]
- Workload Type: [inferred from metrics — e.g. CPU-bound, memory-light]

### Performance Assessment

| Metric        | Observed (Avg/Peak) | Threshold    | Status       |
|---------------|---------------------|--------------|--------------|
| CPU           | XX% / XX%           | <60% / <80%  | ✅/⚠️/🔴     |
| Memory Free   | XX GB               | >10%         | ✅/⚠️/🔴     |
| Disk IOPS     | XX rd / XX wr       | SKU limit    | ✅/⚠️/🔴     |
| Network       | XX MB/s             | SKU limit    | ✅/⚠️/🔴     |

### Pattern Observations
[Describe observed patterns — time-of-day spikes, memory trends, idle periods, etc.]

### Rightsizing Recommendation

**Verdict:** [Scale Up | Scale Down | Right-sized | Investigate]

[Explain why — be specific about which metric is driving the recommendation]

**Suggested SKU:** [SKU name] — [vCPUs] vCPUs, [RAM] GB RAM
**Estimated Cost Impact:** Mention to check Azure Pricing Calculator for final figures.

### Action Items
1. [Specific action — e.g. "Enable Azure Monitor Agent to get memory metrics"]
2. [e.g. "Set CPU alert at 85% with 5-minute window"]
3. [e.g. "Consider Premium SSD if disk latency is a concern"]
```

### Architect Decision Thresholds

| Metric | Scale Up Trigger | Scale Down Trigger | Notes |
|--------|-----------------|--------------------|-------|
| CPU Avg (7-day) | > 70% | < 20% sustained | Don't scale down if any spike > 85% |
| CPU Peak | > 90% repeatedly | < 40% | Consider burstable (B-series) for spiky |
| Memory Free | < 15% consistently | > 60% consistently | Windows adds ~1-2GB overhead |
| Disk IOPS | > 80% of SKU limit | N/A | Upgrade disk tier, not VM |
| Network | > 80% of SKU limit | N/A | Check NIC accelerated networking |

### SKU Recommendation Logic
1. Check if workload is **CPU-bound** → recommend D-series (balanced) or F-series (compute-optimized)
2. If **memory-heavy** → recommend E-series (memory-optimized)
3. If **bursty / dev workloads** → recommend B-series (burstable)
4. If **disk-heavy** → recommend Lsv3-series (storage-optimized) or upgrade disk tier
5. Always prefer `v5` or `v4` generation for cost/performance ratio
6. Mention **Azure Hybrid Benefit** if Windows and not currently using it

See `references/vm-sizes.md` for SKU specs.

---

## Error Handling

| Scenario | Action |
|----------|--------|
| Memory metrics unavailable | Display note: "Memory metrics require Azure Monitor Agent. [Link to docs]". Show CPU/Disk/Net only. |
| VM not found | Suggest checking subscription/resource group scope |
| No data returned | Check if VM was running during the time period; suggest shorter window |
| Metrics sparse | Note data gaps in chart; compute stats from available points only |

---

## Output Summary

At the end of the full response, always close with:

```
📋 Summary: Analyzed [N] VM(s) across [subscription] for [time range].
[N] VMs healthy | [N] VMs need attention | [N] VMs recommend resize
```

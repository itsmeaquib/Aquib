# Azure VM Size Reference

Use this file when making rightsizing recommendations. Cross-reference against the observed VM size from `compute_vm_get`.

## General Purpose (D-series) — Balanced CPU/Memory

| SKU              | vCPUs | RAM (GB) | Temp Disk | Network Mbps | Notes                        |
|------------------|-------|----------|-----------|--------------|------------------------------|
| Standard_D2s_v5  | 2     | 8        | No        | 12,500       | Entry-level balanced         |
| Standard_D4s_v5  | 4     | 16       | No        | 12,500       | Most common workload size    |
| Standard_D8s_v5  | 8     | 32       | No        | 12,500       | Medium-scale apps            |
| Standard_D16s_v5 | 16    | 64       | No        | 12,500       | Large app servers            |
| Standard_D32s_v5 | 32    | 128      | No        | 16,000       | High-concurrency             |
| Standard_D2s_v3  | 2     | 8        | 16 GB     | 1,000        | Older gen, still common      |
| Standard_D4s_v3  | 4     | 16       | 32 GB     | 2,000        | Legacy standard              |
| Standard_D8s_v3  | 8     | 32       | 64 GB     | 4,000        | Legacy mid-tier              |

## Compute Optimized (F-series) — High CPU:Memory Ratio

| SKU              | vCPUs | RAM (GB) | Notes                              |
|------------------|-------|----------|------------------------------------|
| Standard_F2s_v2  | 2     | 4        | CPU-bound workloads                |
| Standard_F4s_v2  | 4     | 8        | Batch processing, gaming servers   |
| Standard_F8s_v2  | 8     | 16       | High-frequency trading, rendering  |
| Standard_F16s_v2 | 16    | 32       | High-performance compute           |

## Memory Optimized (E-series) — High RAM

| SKU              | vCPUs | RAM (GB) | Notes                             |
|------------------|-------|----------|-----------------------------------|
| Standard_E2s_v5  | 2     | 16       | Small in-memory databases         |
| Standard_E4s_v5  | 4     | 32       | SQL Server, SAP workloads         |
| Standard_E8s_v5  | 8     | 64       | Large caches, in-memory analytics |
| Standard_E16s_v5 | 16    | 128      | Mid-scale SAP HANA                |
| Standard_E32s_v5 | 32    | 256      | Large-scale in-memory             |
| Standard_E4s_v3  | 4     | 32       | Legacy, still widely used         |
| Standard_E8s_v3  | 8     | 64       | Legacy mid-tier                   |

## Burstable (B-series) — Dev/Test and Spiky Workloads

| SKU              | vCPUs | RAM (GB) | Base CPU% | Max CPU% | Notes                      |
|------------------|-------|----------|-----------|----------|----------------------------|
| Standard_B1ms    | 1     | 2        | 20%       | 100%     | Minimal test VMs           |
| Standard_B2ms    | 2     | 8        | 60%       | 200%     | Dev/test standard          |
| Standard_B4ms    | 4     | 16       | 90%       | 400%     | Spiky small prod workloads |
| Standard_B8ms    | 8     | 32       | 135%      | 800%     | Bursty medium workloads    |

> ⚠️ B-series accumulates CPU credits. Sustained high CPU depletes credits and throttles to base%. Not suitable for consistently high CPU workloads.

## Storage Optimized (Lsv3-series) — High Disk IOPS

| SKU               | vCPUs | RAM (GB) | Local NVMe | Notes                        |
|-------------------|-------|----------|------------|------------------------------|
| Standard_L8s_v3   | 8     | 64       | 1.92 TB    | High IOPS, low latency        |
| Standard_L16s_v3  | 16    | 128      | 3.84 TB    | Database servers              |
| Standard_L32s_v3  | 32    | 256      | 7.68 TB    | Large-scale data workloads   |

---

## Managed Disk IOPS Limits (for Disk Rightsizing)

| Disk Tier     | Size    | Max IOPS  | Max Throughput |
|---------------|---------|-----------|----------------|
| Standard HDD  | Up to 32TB | 500     | 60 MB/s        |
| Standard SSD  | Up to 32TB | 6,000   | 750 MB/s       |
| Premium SSD   | Up to 32TB | 20,000  | 900 MB/s       |
| Premium SSD v2| Up to 64TB | 80,000 | 1,200 MB/s     |
| Ultra Disk    | Up to 64TB | 160,000| 4,000 MB/s     |

---

## Rightsizing Quick-Reference Matrix

| CPU Avg | Memory Used | Recommended Action                     |
|---------|-------------|----------------------------------------|
| < 20%   | < 40%       | **Scale down** — VM is oversized       |
| 20–60%  | 40–70%      | **Right-sized** — no action needed     |
| 60–80%  | 70–85%      | **Monitor** — approaching threshold    |
| > 80%   | > 85%       | **Scale up** — resource contention     |
| Spiky   | Variable    | **Consider B-series** — burstable      |

---

## Azure Monitor Agent Memory Metrics (KQL reference)

If Azure Monitor Agent is installed, memory metrics appear in Log Analytics via the `InsightsMetrics` table:

```kql
InsightsMetrics
| where Namespace == "Memory"
| where Name == "AvailableMB"
| where TimeGenerated > ago(24h)
| summarize avg(Val), min(Val) by bin(TimeGenerated, 5m), Computer
| render timechart
```

For native platform metrics (no agent), only `Available Memory Bytes` is available via `monitor_metrics_query` on Windows VMs with diagnostics enabled.

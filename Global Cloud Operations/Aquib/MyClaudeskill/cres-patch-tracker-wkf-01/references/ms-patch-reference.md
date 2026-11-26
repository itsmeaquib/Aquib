# Microsoft Patch Reference — Windows Server Cumulative Updates

## How to Find the Latest KB

Always use `web_search` at runtime — patch releases happen monthly (Patch Tuesday = 2nd Tuesday).
Never hardcode a KB number as "latest" — fetch it fresh each time.

**Search query patterns:**

| OS Version | Search Query |
|-----------|-------------|
| Windows Server 2022 | `latest cumulative update Windows Server 2022 KB site:support.microsoft.com` |
| Windows Server 2019 | `latest cumulative update Windows Server 2019 KB site:support.microsoft.com` |
| Windows Server 2016 | `latest cumulative update Windows Server 2016 KB site:support.microsoft.com` |
| Windows Server 2012 R2 | `latest cumulative update Windows Server 2012 R2 KB site:support.microsoft.com` |

Authoritative sources (in order of preference):
1. `https://support.microsoft.com/en-us/topic/windows-server-update-history` (per OS)
2. `https://www.catalog.update.microsoft.com/` (search by KB number)
3. Microsoft Security Update Guide: `https://msrc.microsoft.com/update-guide/`

---

## OS Version Detection

Map `OSName` from Heartbeat to the correct update channel:

| Heartbeat OSName contains | Update channel |
|--------------------------|---------------|
| `2022` | Windows Server 2022 (CB / LTSC 2022) |
| `2019` | Windows Server 2019 (LTSC 2019) |
| `2016` | Windows Server 2016 (LTSC 2016) |
| `2012 R2` | Windows Server 2012 R2 (ESU — check if customer has ESU coverage) |
| `2012` (non-R2) | Windows Server 2012 (ESU — flag as high risk, EOS Oct 2023) |
| `2008` | Windows Server 2008 / R2 — **Critical flag: out of support** |

---

## Compliance Decision Logic

```
Latest MS KB released:  KB_LATEST  (date: D_LATEST)
Server installed KB:    KB_INSTALLED (date: D_INSTALLED)

IF KB_INSTALLED == KB_LATEST                        → ✅ Compliant
IF KB_INSTALLED is predecessor of KB_LATEST
   AND D_LATEST - D_INSTALLED <= 30 days            → ⚠️ Outdated — within grace window
   AND D_LATEST - D_INSTALLED > 30 days             → ⚠️ Outdated — action required
IF no security/cumulative KB in last 90 days        → ❌ Non-Compliant
IF OS is Windows Server 2012 or 2008                → ❌ Non-Compliant + 🚨 EOL flag
```

---

## Supersedence Notes

Microsoft cumulative updates are **cumulative** — each month's CU includes all prior fixes.
A server with KB from 2 months ago is missing 2 months of fixes, not just one.

For security-only updates (not cumulative): these are separate from cumulative updates on
older OS versions (2012 R2, 2016). Confirm which update type the server has installed.

---

## Pending Reboot — Compliance Impact

A server that has the correct KB installed but has a **pending reboot** is considered
**Partially Compliant** — the patch is installed but not yet active in memory.

Flag these separately in the report as:
`⏸️ Pending Reboot — patch installed, reboot required to activate`

---

## Known Quorum Environment Notes

- Most QCloud servers run **Windows Server 2019** or **Windows Server 2022**.
- Patch maintenance windows are typically coordinated — check with Marcus Eberling or the
  customer's change management window before recommending a reboot.
- Post-patch verification KB to always check: `KB5074975` (MSMQ regression CVE-2023-21554)
  — this was a known issue in your environment. If servers are running MSMQ-dependent
  workloads (TIPS, EDI), flag this KB specifically.
- Servers with `CITRIX` or `CTX` in their hostname: validate ICA/HDX service is running
  post-patch before closing compliance.
- Oracle DB servers (`SQL`, `OGSQL` in hostname): coordinate reboot with Craig Barden
  (Oracle/NRM incidents) — do not recommend uncoordinated reboots.

# Log Analysis Reference

This document covers where EDI logs live, how to collect them, and what to look
for when diagnosing QPEC/EDIServ outages.

---

## Log File Types and Locations

### QPECProcessLauncher Log (EDIServ transport layer)

**Location:** On the **EDI server** — typically the EDIServ working directory or
`C:\EDI\log\`. This is a different server from the QPEC server.

**Filename pattern:** `QPECProcessLauncher-<port>-<date>.log`

Examples:
```
QPECProcessLauncher-5713-2026-04-24.log
QPECProcessLauncher-443-2026-04-24.log
```

**Important:** This log is semi-binary. Do NOT try to read it directly with `cat` or
`type`. Use `strings`:

```bash
# Linux
strings QPECProcessLauncher-5713-2026-04-24.log | grep -i "error\|fail\|TrustProxy\|errorhold\|Primary URL\|Connected\|SUCCESS"

# Windows PowerShell — pipe through strings.exe if available, otherwise:
Get-Content .\QPECProcessLauncher-5713-2026-04-24.log -Encoding Byte |
  ForEach-Object { [char]$_ } | Out-String
```

**What it contains:**
- Outbound connection attempts per trading partner (`Primary URL : <hostname>`)
- TCP connect results (`Connected to Socket[addr=...,port=443,...]`)
- TLS handshake errors (`SSLHandshakeException: TrustProxy`)
- File delivery outcomes (`SUCCESS response` or `Sent ... to errorhold directory`)
- Inbound connection errors from trading partners attempting to reach Quorum

**Why this matters:** If files are landing in `C:\EDI\errorhold\`, the cause is here —
not in the QPEC logs. TrustProxy errors, timeouts, and connection resets all appear
in this log.

**Key patterns to search for:**
```bash
# Find all outbound transmission attempts and their outcomes
strings QPECProcessLauncher*.log | grep -E "Primary URL|Connected to Socket|SUCCESS|errorhold|TrustProxy|timed out|refused"

# Find the specific trading partner
strings QPECProcessLauncher*.log | grep -i "<partner-hostname>"
```

---

### QPEC Segregated Logs (MOST IMPORTANT for GPG failures)

**Location:** `C:\Quorum\QPEC\logs\` (confirm with user — may vary)

**Filename pattern:** `qtrace.QPTM.QPEC.<instance>.segregated*.log`

Examples:
```
qtrace.QPTM.QPEC.QPEC_14-2.segregated.log
qtrace.QPTM.QPEC.QPEC_14-4.segregated.1.log
```

**What they contain:**
- Full GPG command with all arguments (including key IDs used)
- Complete GPG error output
- Trading partner identifier for each failed transaction
- Service account context (`{SU}` and `{AO}`)
- Timestamps for each transaction attempt

**Why these are critical:** The master QPEC log does NOT contain GPG details. You
cannot diagnose GPG failures without these files.

**Rotation:** These logs rotate. If the incident started days ago, look for numbered
rotation files (e.g., `.segregated.1.log`, `.segregated.2.log`).

---

### QPEC Master Log

**Filename:** `qtrace.QPTM.QPEC.log`

**What it contains:**
- Session start/stop events
- High-level transaction events
- Service restarts

**Use for:** Establishing timeline, checking if QPEC was running, spotting restarts.
Does NOT contain GPG details — use segregated logs for that.

---

### EDIServ Log

**Filename:** `EDIServ*.log` (may be `EDIServ.log` or dated variants)

**Important:** This log is binary. You cannot `cat` or `type` it directly.

**How to read it:**
```powershell
# On Windows (PowerShell):
Get-Content .\EDIServ.log -Encoding Byte | ForEach-Object { [char]$_ } | Out-String
# Or use strings.exe if available:
strings.exe .\EDIServ.log
```

```bash
# On Linux (if file was transferred):
strings EDIServ.log
```

**What it contains:**
- AS2/SFTP connection events
- File transfer success/failure
- Transport-layer errors (network, auth, certificate issues)

**Use for:** Diagnosing transport failures (not encryption failures). If EDIServ is
erroring but QPEC is not, the issue is at the network/protocol layer.

---

## Log Collection Request Template

When asking the user to collect logs, use this as a template:

```
Please collect the following from QPEC server <SERVER_HOSTNAME>:

From C:\Quorum\QPEC\logs\ (or your QPEC log directory):
1. All files matching: qtrace.QPTM.QPEC.*.segregated*.log
2. The main log: qtrace.QPTM.QPEC.log
3. If transport errors suspected: EDIServ.log (and any numbered rotations)

Zip them up and attach to the ADO ticket, or share via the usual path.
Estimated size: typically 1-50 MB for a few days of logs.
```

---

## Key Search Commands

### Find all GPG failures and their context

```powershell
# PowerShell — search all segregated logs
Select-String -Path "qtrace.QPTM.QPEC.*.segregated*.log" -Pattern "gpg: " |
  Select-Object LineNumber, Line | Format-Table -AutoSize

# With context — show 5 lines before each GPG error
Select-String -Path "qtrace.QPTM.QPEC.*.segregated*.log" -Pattern "gpg: " -Context 5,0
```

```bash
# Linux bash — if logs were transferred
grep -B5 "gpg: " qtrace.QPTM.QPEC.*.segregated*.log
```

### Find the earliest failure

```powershell
# First occurrence of any GPG error
Select-String -Path "qtrace.QPTM.QPEC.*.segregated*.log" -Pattern "gpg: " |
  Select-Object -First 1

# Check each file individually to find the true earliest
foreach ($f in Get-ChildItem "qtrace.QPTM.QPEC.*.segregated*.log") {
  $first = Select-String -Path $f.Name -Pattern "gpg: " | Select -First 1
  if ($first) { Write-Host "$($f.Name): $($first.Line)" }
}
```

### Count distinct error types

```powershell
Select-String -Path "qtrace.QPTM.QPEC.*.segregated*.log" -Pattern "gpg: " |
  Select-Object -ExpandProperty Line |
  Sort-Object | Group-Object | Sort-Object Count -Descending |
  Format-Table -AutoSize
```

### Extract all unique key IDs referenced

```powershell
# Signing key IDs (-u argument)
Select-String -Path "qtrace.QPTM.QPEC.*.segregated*.log" -Pattern "\-u [A-F0-9]{8}" |
  Select-Object -ExpandProperty Matches | Select-Object -ExpandProperty Value | Sort -Unique

# Recipient key IDs (-r argument)  
Select-String -Path "qtrace.QPTM.QPEC.*.segregated*.log" -Pattern "\-r [A-F0-9]{8}" |
  Select-Object -ExpandProperty Matches | Select-Object -ExpandProperty Value | Sort -Unique
```

### Count total failures

```powershell
(Select-String -Path "qtrace.QPTM.QPEC.*.segregated*.log" -Pattern "sign\+encrypt failed").Count
```

---

## What to Look For — Diagnostic Checklist

When reviewing logs, answer these questions:

### Timeline
- [ ] What timestamp does the FIRST failure appear? (Not when it was reported)
- [ ] Do failures start at a specific time that correlates with a known change?
- [ ] Are failures continuous or do they stop and start?

### Scope
- [ ] Which trading partners are failing? (All or just some?)
- [ ] Do any trading partners succeed while others fail?
- [ ] Are there any successful GPG operations in the same timeframe?

### Error pattern
- [ ] Are files in `C:\EDI\errorhold\`? → Check QPECProcessLauncher log first
- [ ] Is the error "TrustProxy" / `SSLHandshakeException`? → Type C (missing cert in Personal store)
- [ ] Does `Connected to Socket` appear before the error? → TCP works; it's TLS not network
- [ ] Is the error "secret key not available"? → Type A (QPTM signing key config)
- [ ] Is the error "public key not found"? → Type B (missing recipient key)
- [ ] Are both Type A and B present? → DB refresh caused both issues simultaneously
- [ ] Is the error "no valid OpenPGP data"? → Encoding issue during key import

### Service account
- [ ] What is `{SU}` in the log entries? (actual Windows service account)
- [ ] What is `{AO}` in the log entries? (QPTM-configured account)
- [ ] Do they match what's expected for this environment?

### Key IDs
- [ ] What signing key ID (`-u`) is QPEC trying to use?
- [ ] Does that key ID exist in the UAT keyring (`--list-secret-keys`)?
- [ ] What recipient key IDs (`-r`) are being referenced?
- [ ] Do those keys exist in the keyring (`--list-keys`)?

---

## Log Evidence to Include in the RCA

Always copy the exact log entry verbatim into the RCA, including:
- The timestamp
- The `{SU}` and `{AO}` context
- The full `GPG arguments:` line
- The complete error output

Example of well-documented log evidence:
```
From qtrace.QPTM.QPEC.QPEC_14-4.segregated.1.log, earliest failure at
2026-04-25 13:00:31:

  [QPEC_SCHEDULER{SU}QBS_UAT17_QPEC_USER{AOC}]
  GPG arguments: -r D2E62452 -u E66B8C0B --homedir "C:\GNU\GnuPG" -es <file>
  gpg: skipped "E66B8C0B": secret key not available
  gpg: [stdin]: sign+encrypt failed: secret key not available
```

This makes the RCA self-contained and verifiable without having to go back to the logs.

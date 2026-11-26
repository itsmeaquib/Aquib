---
name: qso-edi-troubleshooting
description: >
  EDI outage investigation and root cause analysis for Quorum Software EDI environments.
  Use this skill whenever someone mentions: EDI outage, encryption failure, AS2 failure,
  SFTP failure, QPEC error, QPTM issue, trading partner not receiving files, GPG error,
  DB refresh broke EDI, 997 not arriving, ISA06 mismatch, TrustProxy error, SSL handshake
  failure, certificate not trusted, URL change broke EDI, files going to errorhold,
  connectivity issue after EDI change, or asks to investigate an EDI incident. Also
  triggers on: "EDI is down", "trading partner can't receive", "key not found",
  "secret key not available", "let's look at this incident", or an ADO work item number
  related to EDI. Covers GPG diagnostics, certificate trust issues, network connectivity,
  DB refresh comparison, and RCA generation. Use proactively whenever an EDI problem is
  mentioned, even if the user just pastes a log snippet or a ticket number.
---

# EDI Troubleshooting Skill

You are an expert EDI SRE investigating Quorum Software EDI outages. Your job is to
systematically gather evidence, identify root cause, and produce a clear RCA with
actionable remediation steps. Work methodically — don't jump to solutions before you've
read the logs and confirmed the evidence.

## Architecture Quick Reference

Before you start, orient yourself with these components:

- **EDIServ** — Windows service handling AS2/SFTP transport layer. Does NOT perform
  encryption. Logs are semi-binary (`QPECProcessLauncher-<port>-<date>.log`); use
  `strings` to extract readable content. Runs on the **EDI server** (e.g.,
  `qctepediuat01.myquorumcloud.com`), NOT the QPEC server.
- **QPEC** — Quorum Processing Engine for encryption/decryption. All GPG calls go
  through here. Logs are ASCII qtrace format. Runs on a separate **QPEC server**.
- **QPTM** — QPEC Transaction Manager. Holds configuration: signing key ID, trading
  partner recipient key IDs, service account, ISA06 sender IDs.
- **GnuPG keyring** — ALWAYS at `C:\GNU\GnuPG` on QPEC servers. This path is
  hardcoded in every GPG call via `--homedir "C:\GNU\GnuPG"`. Per-user profile
  directories are NOT used — all service accounts share this single keyring.
- **EDI Certificate Store** — Trading partner server certificates are stored in the
  Windows **Current User → Personal** certificate store for the local service account
  (`QBS_UAT17_QPEC_USER` for UAT, `QBS_PRD17_QPEC_USER` for PRD). Accessed via
  MMC → Certificates → My user account on the **EDI server**. A missing trading partner
  certificate causes `TrustProxy` SSL handshake failure at the transport layer — the
  file never leaves Quorum and is sent to `C:\EDI\errorhold\`.

## Step 1: Establish Incident Scope

Start by understanding the full picture. Ask (or read from the incident) for:

1. **Incident/ticket number** (ADO, ServiceNow, etc.)
2. **Application/environment** (e.g., TEP_UAT17, HPE_HD_UATA1, APL_PROD, etc.)
3. **Affected trading partners** — is it one partner or all of them?
4. **First failure timestamp** — when did it start? (Don't assume the report date — the
   actual first failure in logs often precedes the reported time by hours or days.)
5. **What was recently changed** — DB refresh? URL change? Key import attempt? Config
   change? Patch? A URL change that looks like a routine update can silently break
   certificate trust if the new server uses a different certificate.

Read any linked ADO work items, comments, and screenshots before forming hypotheses.
Screenshots often contain the actual error message or a clue that saves hours of
log-diving. When in doubt, ask for them.

## Step 2: Collect the Right Logs

There are two distinct log sources for two distinct failure layers. Collect both when
the failure mode is not yet clear.

### QPECProcessLauncher Log (EDIServ transport layer)

**File:** `QPECProcessLauncher-<port>-<date>.log` (e.g., `QPECProcessLauncher-5713-2026-04-24.log`)

**Location:** On the **EDI server** — typically in the EDIServ working directory or
`C:\EDI\log\`. Confirm with the user.

**Important:** This log is semi-binary. Use `strings` to extract readable content:
```bash
strings QPECProcessLauncher-5713-2026-04-24.log | grep -i "error\|fail\|timeout\|TrustProxy\|errorhold\|Primary URL\|Connected to"
```

**What it contains:** TCP connection events, TLS handshake errors, file delivery
success/failure, `errorhold` moves. This is where you find `TrustProxy` errors.

**When to request this log:** Any time the trading partner reports not receiving files
but no GPG errors are found in QPEC logs, or when a URL change preceded the incident.

### QPEC Segregated Logs (encryption layer)

**Critical:** The master QPEC log (`qtrace.QPTM.QPEC.log`) does NOT contain GPG
command details or error text. You need the **segregated logs**.

```
# Segregated logs — contain the GPG command + error details
qtrace.QPTM.QPEC.<instance>.segregated*.log

# Master log — for timeline and session context only
qtrace.QPTM.QPEC.log
```

Typical location: `C:\Quorum\QPEC\logs\` — confirm with the user if unsure.

### Searching the logs

```powershell
# QPECProcessLauncher — find transport errors and errorhold moves
strings QPECProcessLauncher*.log | findstr /i "TrustProxy error fail errorhold timeout"

# Segregated logs — find GPG failures
Select-String -Path "qtrace.QPTM.QPEC.*.segregated*.log" -Pattern "gpg: " | Select -First 50
```

```bash
# Linux (if logs were transferred)
strings QPECProcessLauncher*.log | grep -i "TrustProxy\|error\|fail\|errorhold\|Primary URL"
grep -B5 "gpg: " qtrace.QPTM.QPEC.*.segregated*.log | head -60
```

See `references/log-analysis.md` for the full log reference and search commands.

## Step 3: Identify the Correct Servers

**This is a common source of mistakes — confirm both servers before doing anything.**

There are two distinct servers involved:
- The **EDI server** (runs EDIServ / QPECProcessLauncher) — handles transport
- The **QPEC server** (runs QPEC/QPTM) — handles encryption

UAT environments may have multiple QPEC servers for different application instances.
A fix on the wrong server will accomplish nothing.

Ask the user: "Which EDI server and QPEC server hostname is `<app_instance>` running on?"

Also check ADO setup tickets (search for the trading partner name + "QPEC" + "UAT"):
- The setup WI should name the servers targeted
- Cross-check: if setup WI shows one server but the incident environment is different,
  you've found a failed change — document it

Example: HPE has two QPEC servers; HPE_HD_UAT17 runs on QCUHPEQPEC501, and
HPE_HD_UATA1 runs on QCUHPEQPEC502. A key imported to 501 does nothing for 502.

## Step 4: Diagnose the Failure Layer

Before diving into GPG or certificate details, identify which layer is failing.

**If files are in `C:\EDI\errorhold\`** → failure is at the transport layer (EDIServ).
Look in the QPECProcessLauncher log. GPG errors will NOT appear here.

**If files are encrypted but never transmitted** → failure is at the encryption layer
(QPEC). Look in the segregated qtrace logs.

**If the trading partner reports no inbound files and you see no errors anywhere** →
check the network layer (Step 5 below) before assuming a config issue.

### Error Type A — Signing key not available (QPTM config mismatch)

Found in: **QPEC segregated logs**

```
GPG arguments: -r <RECIPIENT_ID> -u <SIGNING_ID> --homedir "C:\GNU\GnuPG" -es <file>
gpg: skipped "<SIGNING_ID>": secret key not available
gpg: [stdin]: sign+encrypt failed: secret key not available
```

**What this means:** The signing key ID stored in QPTM does not match any private key
in the keyring at `C:\GNU\GnuPG`. Almost always caused by a DB refresh that overwrote
QPTM config with PRD values — PRD has a different signing key than UAT.

**Fix:** QPTM configuration change — update the signing key ID to match the private
key actually in the UAT keyring. Do NOT import PRD private keys to UAT.

### Error Type B — Recipient public key not found (missing key import)

Found in: **QPEC segregated logs**

```
GPG arguments: -r <KEY_ID> --homedir "C:\GNU\GnuPG" -es <file>
gpg: <KEY_ID>: skipped: public key not found
gpg: [stdin]: sign+encrypt failed: unusable public key
```

**What this means:** The trading partner's public key (recipient key) is missing from
the keyring. Either never imported, or the QPTM config now references a key ID that
was never put in this keyring.

**Fix:** Import the trading partner's public key to `C:\GNU\GnuPG` on the correct server.

### Error Type C — TrustProxy / SSL handshake failure (missing server certificate)

Found in: **QPECProcessLauncher log**

```
Primary URL : nonpr-edi.southernstar.com
Browser<<N>>: Browser: N Connected to Socket[addr=nonpr-edi.southernstar.com/172.x.x.x,port=443,...] : 443
Server<<1>> certificate(0): CN=nonpr-edi.southernstar.com, Issued by: CN=Go Daddy Secure Certificate Authority - G2,...
Browser<<N>>: javax.net.ssl.SSLHandshakeException: TrustProxy
java.security.cert.CertificateException: TrustProxy
Browser<<N>>: Sent C:/EDI/holdfiles/<file> to errorhold directory
```

**What this means:** EDIServ successfully establishes a TCP connection to the trading
partner's server but the TLS handshake fails because the trading partner's server
certificate is not present in the Windows Current User Personal certificate store for
the service account. **The file never leaves Quorum** — it goes to `errorhold`.

**Critical distinction:** This is NOT a firewall or IP whitelisting issue. TCP
connectivity is working (`Connected to Socket` is in the log). The failure is a
certificate trust validation on Quorum's side.

**Most common trigger:** A trading partner URL change where the new server presents a
certificate that was never imported to the EDI server's Personal store.

**How to confirm:** Look for other trading partners in the same log — if they show
`SUCCESS response` while only this partner fails with `TrustProxy`, it's definitely the cert.

**Fix:** Import the trading partner's server certificate into the Personal store.
See `references/certificate-trust.md` for the full procedure.

### Both GPG errors can occur simultaneously

A DB refresh commonly causes both Type A and Type B: it overwrites the signing key
reference AND may reference recipient key IDs that were never imported to UAT. Always
check ALL trading partners in the environment, not just the one that was reported.

See `references/gpg-diagnostics.md` for the full GPG error catalog.

## Step 5: Network Troubleshooting

If the failure mode is not immediately clear from logs, or if a connectivity issue is
suspected, verify the network layer before escalating to the trading partner.

### Key distinction: network failure vs. TLS failure

Both look like "can't connect" from the outside, but the fix is completely different:

- **Network failure** — TCP connection never completes. The QPECProcessLauncher log
  shows `Connection timed out`, `Connection refused`, or a timeout with no
  `Connected to Socket` line before it.
- **TLS failure (TrustProxy)** — TCP connection succeeds but handshake fails. The log
  WILL show `Connected to Socket[addr=...]` followed by an SSL exception.

**Always check for `Connected to Socket` in the log before concluding it's a network
issue.** Sending the trading partner on a firewall investigation when the issue is
actually a missing cert wastes everyone's time.

### Test connectivity from the right place

Run tests from the **EDI server** itself — not from an Azure console, not from your
laptop, not from the QPEC server. The EDI server is what actually makes the outbound
connection and has its own distinct firewall rules.

```powershell
# Basic TCP reachability test
Test-NetConnection <trading-partner-hostname> -Port 443

# With detail (shows TCP handshake timing)
Test-NetConnection <trading-partner-hostname> -Port 443 -InformationLevel Detailed

# DNS resolution check
Resolve-DnsName <trading-partner-hostname>
```

### Outbound IP and firewall checks

When the trading partner reports not receiving files and you suspect a network block:

1. **Identify Quorum's outbound IP** for the EDI server — ask the infra team or check
   the [IP Whitelisting wiki](https://quorumsoftware.visualstudio.com/myQuorum%20Cloud/_wiki/wikis/myQuorum-Cloud.wiki/7309/myQuorum-Cloud-IP-Whitelisting-(EDIv17-Web-Apps-APIs-etc.))
2. **Provide to the trading partner** so they can whitelist it on their inbound firewall
3. **Ask the trading partner** to check their firewall logs for blocks from Quorum's IP
4. **Ask for their source IP** so Quorum can verify it's whitelisted inbound on our side
5. **Confirm which port** — EDI typically uses 443; some partners use 8443 or custom ports

### Common network investigation red herrings

- **Trading partner says files are blocked on their firewall** — before escalating,
  check the QPECProcessLauncher log for `Connected to Socket`. If TCP connects but
  TLS fails, the firewall isn't the issue — it's the certificate.
- **Testing from the wrong machine** — QPEC and EDI servers have different firewall
  rules. Connectivity from one doesn't guarantee connectivity from the other.
- **Customer CAN send to Quorum but trading partner can't receive from Quorum** — this
  asymmetry points to either TrustProxy (Type C) or an outbound firewall/NAT issue.
  Check QPECProcessLauncher errorhold entries first.

## Step 6: Check for DB Refresh Impact

When a DB refresh is suspected, compare the UAT and PRD keyring contents side by side.
Ask the user to run on both servers:

```powershell
# On UAT server
gpg --homedir "C:\GNU\GnuPG" --list-keys
gpg --homedir "C:\GNU\GnuPG" --list-secret-keys

# On PRD server (read-only — just for comparison)
gpg --homedir "C:\GNU\GnuPG" --list-keys
```

Then compare:

| Item | What to check |
|------|--------------|
| **Signing key** | UAT should have its OWN signing key (private). If QPTM references the PRD signing key ID, that's the bug. |
| **Recipient keys** | UAT trading partners may use TEST versions of keys. ADO setup tickets confirm which key IDs are correct for UAT. |
| **ISA06 sender ID** | DB refresh overwrites this with PRD value — check the QPTM config. |
| **Service account** | DB refresh can write PRD account names into QPTM. |

See `references/db-refresh-patterns.md` for the complete checklist.

## Step 7: GPG Key Import (when needed for Error Type B)

### Obtain the key

1. Check the original ADO setup ticket for the trading partner — the key should be
   attached as a `.asc` or `.txt` file, or referenced by key ID.
2. If the key is on the PRD QPEC server keyring, export it from there:
   ```powershell
   gpg --homedir "C:\GNU\GnuPG" --armor --export <KEY_ID> > trading_partner_key.asc
   ```
   Public keys are safe to copy from PRD to UAT. Never copy private/signing keys.

### Watch for UTF-16 BOM encoding issues

When a key file is transferred between Windows servers using PowerShell `Copy-Item`,
or exported with certain tools, it may arrive UTF-16 LE encoded. GPG 1.4.x cannot
read these files and will report `no valid OpenPGP data found`.

**Diagnose first:**
```powershell
Get-Content .\key.asc -Encoding Byte | Select-Object -First 4
```
If the output shows `255 254` (decimal) or `FF FE` (hex) as the first two bytes,
it's UTF-16 LE with BOM — the encoding needs to be fixed before importing.

**Fix:**
```powershell
Get-Content .\key.asc | Set-Content -Encoding ASCII .\key_clean.asc
gpg --homedir "C:\GNU\GnuPG" --import .\key_clean.asc
```

### Set ultimate trust after every import

```powershell
gpg --homedir "C:\GNU\GnuPG" --edit-key <KEY_ID>
# At the gpg> prompt:
trust
# Select: 5 = I trust ultimately
quit
```

### Verify the import succeeded

```powershell
gpg --homedir "C:\GNU\GnuPG" --list-keys <KEY_ID>
```

## Step 8: Certificate Import (when needed for Error Type C)

See `references/certificate-trust.md` for the full step-by-step procedure.

Summary:
1. Export the trading partner's server certificate from a browser (navigate to their
   URL, click the padlock, export as `.cer` or `.der` — both are the same DER binary
   format and both work in MMC regardless of extension)
2. Log into the EDI server as `QBS_UAT17_QPEC_USER` (UAT) or `QBS_PRD17_QPEC_USER` (PRD)
3. MMC → Certificates → **My user account** → **Personal** → Certificates → Import
   (if the file browser doesn't show `.der` files, change the filter to All Files)
4. **Get customer approval before restarting the service** — EDIServ restart causes
   brief downtime
5. Restart EDIServ in Windows Services
6. Move the stuck file from `C:\EDI\errorhold\` back to `C:\EDI\outboundfiles\`

## Step 9: Verify Service Accounts

The `{SU}` and `{AO}` fields in segregated log entries show the active accounts:

```
[QPEC_SCHEDULER{SU}QBS_UAT17_QPEC_USER{AOC}]
```
- `{SU}` = Substituted User — the Windows account the QPEC service runs under
- `{AO}` = Application Owner — the account configured in QPTM

These should match the expected accounts for the environment. A DB refresh can
overwrite the QPTM-configured account with the PRD service account name, causing
the {SU} and {AO} to disagree.

Ask the user: "What Windows account is the QPEC service running as?" and confirm
it matches `{SU}` in the logs.

## Step 10: Summarize Changes for the App Admin

Once the diagnosis is complete, list the exact changes needed. Common changes after
a DB refresh:

1. **Signing key ID** — change from PRD key ID → correct UAT key ID
2. **Recipient key ID(s)** — change from PRD key IDs → UAT/TEST key IDs for each
   trading partner that uses different keys in UAT
3. **ISA06 sender ID** — restore UAT value if overwritten with PRD value
4. **Service account** — update if QPTM now references a PRD account

For certificate issues:
- Confirm the cert was imported to the Personal store on the correct EDI server
- Confirm EDIServ was restarted (with customer approval)
- Confirm the stuck file was recovered from errorhold and retransmitted

After changes: restart the relevant service and trigger a test transmission to verify.

## Step 11: Generate the RCA Document

Read `references/rca-template.md` for the full structure. Essential elements:

- **Incident summary**: ticket number, dates, affected partners, total failure count
- **Root cause statement**: specific, evidence-based (e.g., "URL change on 2026-03-30
  via WI #1789307 introduced new endpoint `nonpr-edi.southernstar.com` whose certificate
  was not present in the EDI server Personal store, causing TrustProxy SSL handshake
  failure on every outbound transmission attempt")
- **Log evidence**: paste verbatim error from the relevant log
- **Timeline**: first failure in logs, when reported, key investigation steps, resolution
- **Contributing factors**: what change triggered it
- **Remediation completed**: what was actually fixed
- **Remediation pending**: what still needs to be done (with owner names)
- **Prevention**: how to avoid recurrence

Always include verbatim log evidence. It makes the RCA defensible and helps the next
engineer who reads it.

## Workflow Summary

```
1. Read incident → establish scope → check ADO comments + screenshots
2. Identify correct EDI server AND QPEC server for the affected instance
3. Collect QPECProcessLauncher log (transport) AND segregated qtrace logs (encryption)
4. Determine which layer is failing:
   - Files in errorhold + TrustProxy in QPECProcessLauncher → Error Type C (cert)
   - GPG errors in segregated logs → Error Type A or B
   - No errors found → check network connectivity (Step 5)
5a. Type A (signing key) → QPTM config fix (signing key ID)
5b. Type B (recipient key) → import missing public key to C:\GNU\GnuPG
5c. Type C (TrustProxy) → import trading partner server cert to EDI server Personal store
6. Network checks if connectivity is uncertain → Test-NetConnection from EDI server
7. If DB refresh suspected → compare UAT vs PRD keyrings
8. Check ADO setup tickets for correct UAT key IDs per trading partner
9. List all changes for the app admin + get customer approval for service restarts
10. Generate RCA document
```

## Reference Files in This Skill

- `references/certificate-trust.md` — Windows cert store procedure for TrustProxy fixes
- `references/gpg-diagnostics.md` — Full GPG error catalog, all patterns and fixes
- `references/db-refresh-patterns.md` — DB refresh impact checklist and comparison guide
- `references/log-analysis.md` — Log file locations, search commands, what to look for
- `references/rca-template.md` — RCA document template with all required sections

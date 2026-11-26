# Certificate Trust Reference — EDI Servers

This document covers how trading partner server certificates work in Quorum EDI
environments and the step-by-step procedure for importing them when missing.

---

## Background

EDIServ (the QPECProcessLauncher service) validates the TLS certificate presented by
a trading partner's server when making outbound AS2 connections. Unlike a standard
browser, it does NOT use the system-wide Windows certificate store — it uses the
**Current User** certificate store for the **local service account** that the EDI
service runs under.

This means:
- Certificates installed under the computer account are **not used**
- Certificates installed under a different user account are **not used**
- Only certs in the Personal store of the specific service account matter

### Service accounts by environment

| Environment | Local service account |
|-------------|----------------------|
| UAT | `QBS_UAT17_QPEC_USER` |
| PRD | `QBS_PRD17_QPEC_USER` |

You must be logged into the EDI server **as that account** (not as an admin, not via
runas) to access the correct certificate store.

---

## When This Becomes a Problem

The most common trigger is a **trading partner URL update**. When a new endpoint is
configured in QPTM (via a change request WI), the new server may present a certificate
that was never imported. The old URL's cert was in the store; the new one isn't.

Symptoms:
- Trading partner reports no inbound files
- No GPG errors in QPEC logs
- QPECProcessLauncher log shows `TrustProxy` and file moved to `errorhold`
- `Connected to Socket` IS present (TCP works fine; only TLS fails)
- Other trading partners in the same log are delivering successfully

---

## Certificate Store Layout

The Personal store contains the **leaf certificates** of each trading partner's server
(not CA chains — those live in Trusted Root and Intermediate stores). Each certificate
in the Personal store corresponds to one trading partner endpoint.

Checking the store:
1. RDP into the EDI server as `QBS_UAT17_QPEC_USER` (or PRD equivalent)
2. Start → type `MMC` → Enter
3. File → Add/Remove Snap-In → Certificates → **My user account** → Finish → OK
4. Expand **Personal** → **Certificates**

You should see one entry per active trading partner endpoint (e.g.,
`*.enercross.com`, `tmveditest.tenaska.com`, `editest.enbridge.com`, etc.).

---

## Importing a Missing Trading Partner Certificate

### Step 1 — Export the certificate from a browser

1. Open a browser and navigate to the trading partner's endpoint URL
   (e.g., `https://nonpr-edi.southernstar.com`)
2. Click the padlock icon → **Certificate** (or "Connection is secure" → Certificate)
3. Go to the **Details** tab
4. Click **Export** (or **Copy to File** depending on browser)
5. Choose format: **DER encoded binary** (`.cer` or `.der` — they are identical formats;
   either extension works in MMC)
6. Save to a location accessible from the EDI server

> **Note:** Export only the leaf certificate (the server's own cert), not the full chain.
> The CA chain (Trusted Root + Intermediate) is already present in the store.

### Step 2 — Transfer the file to the EDI server

Copy the `.cer` or `.der` file to the EDI server via whatever transfer method is
standard in your environment (RDP clipboard, shared drive, etc.).

### Step 3 — Import into the Personal store

1. On the EDI server, logged in as `QBS_UAT17_QPEC_USER`:
2. Start → type `MMC` → Enter
3. File → Add/Remove Snap-In → Certificates → **My user account** → Finish → OK
4. Expand **Personal** → right-click **Certificates** → All Tasks → **Import**
5. In the import wizard:
   - Click **Next**
   - Browse to the `.cer` / `.der` file. If you don't see it, change the file type
     filter to **All Files (`*.*`)** — the dialog defaults to `.cer` and may hide `.der`
   - Place the certificate in: **Personal** (should be pre-selected)
   - Click **Finish**
6. Confirm the new certificate appears in the Personal store list with the correct
   CN (e.g., `nonpr-edi.southernstar.com`)

### Step 4 — Get customer approval for the restart

EDIServ must be restarted for the new certificate to take effect. A restart causes
brief downtime for all trading partners on that EDI instance. Always notify the
customer and get approval before proceeding.

### Step 5 — Restart EDIServ

1. Open **Services** (`services.msc`) on the EDI server
2. Find the EDIServ service (may be named `EDIServ` or similar)
3. Right-click → **Restart**
4. Confirm the service returns to **Running** status

### Step 6 — Recover the stuck file from errorhold

Files that failed due to TrustProxy are moved to `C:\EDI\errorhold\`. They need to
be moved back to trigger retransmission:

```powershell
# List files in errorhold
Get-ChildItem C:\EDI\errorhold\

# Move a specific file back to outboundfiles for retransmission
Move-Item C:\EDI\errorhold\<filename> C:\EDI\outboundfiles\
```

After moving, EDIServ should pick up the file automatically on its next poll cycle.
Watch the QPECProcessLauncher log for a `SUCCESS response` line to confirm delivery.

---

## Verifying the Fix

In the QPECProcessLauncher log, a successful transmission looks like:

```
Primary URL : nonpr-edi.southernstar.com
Browser<<N>>: Browser: N Connected to Socket[addr=nonpr-edi.southernstar.com/172.x.x.x,port=443,...] : 443
Browser<<N>>: SUCCESS response for sending file C:/EDI/holdfiles/<filename>
```

If `TrustProxy` still appears after the restart, double-check:
- The certificate was imported to **Personal** (not Trusted Root or Intermediate)
- You are logged in as the correct service account when viewing the store
- The CN on the imported cert matches the hostname in the `Primary URL` line in the log

---

## Prevention

Whenever a trading partner URL is updated via a QPTM change request WI, the engineer
making the change should also:

1. Check whether the new endpoint's certificate is already in the Personal store
2. If not, export and import it before the change goes live
3. Note the cert import in the WI resolution comments

This prevents the pattern where a URL change closes cleanly but EDI silently starts
failing for that partner the moment the first file is sent.

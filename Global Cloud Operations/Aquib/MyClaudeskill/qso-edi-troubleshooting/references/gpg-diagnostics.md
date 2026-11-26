# GPG Diagnostics Reference

This document catalogs every GPG error pattern seen in QPEC environments,
with diagnosis steps and the correct fix for each.

---

## How to Read a QPEC Segregated Log Entry

A typical block in `qtrace.QPTM.QPEC.<instance>.segregated*.log` looks like:

```
2026-04-25 13:00:31.456 [THREAD-123]
[QPEC_SCHEDULER{SU}QBS_UAT17_QPEC_USER{AOC}]
Trading partner: EMERA (ID: 618091672_838611739)
GPG arguments: -r 6B216B1D -u F8F1C5B0 --homedir "C:\GNU\GnuPG" -es C:\Quorum\tmp\out123.edi
Error output:
gpg: 6B216B1D: skipped: public key not found
gpg: [stdin]: sign+encrypt failed: unusable public key
```

Key fields to extract:
- **Timestamp** — when the failure occurred
- **`{SU}`** — Windows service account running QPEC (Substituted User)
- **`{AO}`** — account configured in QPTM (Application Owner)
- **`-r <KEY_ID>`** — recipient (trading partner public key ID)
- **`-u <KEY_ID>`** — signing key (your organization's private key ID)
- **`--homedir`** — always `C:\GNU\GnuPG` (hardcoded, shared for all accounts)
- **GPG error text** — the actual diagnosis

---

## Error Catalog

### Error 1: Secret key not available (Type A — QPTM config mismatch)

**Log pattern:**
```
gpg: skipped "<KEY_ID>": secret key not available
gpg: [stdin]: sign+encrypt failed: secret key not available
```

**What it means:**
The `-u <KEY_ID>` argument (signing key ID from QPTM config) does not match any
private key in `C:\GNU\GnuPG`. QPTM is configured with the wrong key ID.

**Most common cause:** DB refresh overwrote UAT QPTM config with PRD values. The PRD
signing key private key doesn't exist in the UAT keyring.

**Diagnosis steps:**
1. Note the key ID from the error (the value after `skipped "..."`)
2. Run on the QPEC server:
   ```powershell
   gpg --homedir "C:\GNU\GnuPG" --list-secret-keys
   ```
3. If the key ID from the error is NOT in the list → confirm this is a QPTM config issue
4. Look at what key IS in the list → that's the correct signing key ID for QPTM

**Fix:**
Update QPTM signing key ID to match the private key actually present in the keyring.
Do NOT import the PRD private key to UAT.

---

### Error 2: Public key not found (Type B — missing recipient key)

**Log pattern:**
```
gpg: <KEY_ID>: skipped: public key not found
gpg: [stdin]: sign+encrypt failed: unusable public key
```

**What it means:**
The `-r <KEY_ID>` argument (trading partner recipient key from QPTM) does not exist
in `C:\GNU\GnuPG`. The public key needs to be imported.

**Most common causes:**
- DB refresh introduced a new key ID reference that was never imported to this server
- Key was imported to the wrong QPEC server (e.g., 501 instead of 502)
- Key import was attempted but failed silently (encoding issue)

**Diagnosis steps:**
1. Note the key ID from the error
2. Run on the QPEC server:
   ```powershell
   gpg --homedir "C:\GNU\GnuPG" --list-keys <KEY_ID>
   ```
3. If nothing returns → key is missing from this server's keyring
4. Check if the key exists on another QPEC server (wrong server import)
5. Check the ADO setup ticket for this trading partner → was it imported to the right server?

**Fix:**
Import the public key from the correct source (see Key Import Procedure below).

---

### Error 3: No valid OpenPGP data found (encoding issue)

**Log pattern (or seen during manual import attempt):**
```
gpg: no valid OpenPGP data found
gpg: Total number processed: 0
```

**What it means:**
The key file cannot be parsed by GPG. Almost always a UTF-16 encoding issue.

**Diagnosis:**
```powershell
Get-Content .\key.asc -Encoding Byte | Select-Object -First 4
```
- `255 254` (decimal) or `FF FE` (hex) as first two bytes = UTF-16 LE BOM → encoding issue
- `45 45 45 45` (decimal) or `2D 2D 2D 2D` (hex, which is `----`) = ASCII/UTF-8 → file is OK

**Fix:**
```powershell
Get-Content .\key.asc | Set-Content -Encoding ASCII .\key_clean.asc
gpg --homedir "C:\GNU\GnuPG" --import .\key_clean.asc
```

---

### Error 4: Key untrusted / invalid user ID

**Log pattern:**
```
gpg: WARNING: This key is not certified with a trusted signature!
gpg: There is no indication that the signature belongs to the owner.
```

Or during encryption:
```
gpg: <KEY_ID>: There is no assurance this key belongs to the named user
gpg: [stdin]: sign+encrypt failed: unusable public key
```

**What it means:**
The key was imported but ultimate trust was not set.

**Fix:**
```powershell
gpg --homedir "C:\GNU\GnuPG" --edit-key <KEY_ID>
# At gpg> prompt:
trust
# Select 5 = I trust ultimately
quit
```

---

### Error 5: Expired key

**Log pattern:**
```
gpg: <KEY_ID>: skipped: Unusable public key
gpg: There are no valid recipients for the encryption
```

**Diagnosis:**
```powershell
gpg --homedir "C:\GNU\GnuPG" --list-keys <KEY_ID>
```
Look for `[expired: YYYY-MM-DD]` next to the key.

**Fix:**
The trading partner needs to provide a new key. In UAT, this is uncommon but does
occur with test keys that have short expiration periods.

---

## Key Import Procedure (Standard)

Use this every time a public key needs to be imported:

```powershell
# 1. Check the byte encoding of the key file first
Get-Content .\key.asc -Encoding Byte | Select-Object -First 4

# 2a. If UTF-16 BOM detected (FF FE), convert first:
Get-Content .\key.asc | Set-Content -Encoding ASCII .\key_clean.asc
$importFile = ".\key_clean.asc"

# 2b. If ASCII/UTF-8 (starts with 2D 2D = "--"):
$importFile = ".\key.asc"

# 3. Import
gpg --homedir "C:\GNU\GnuPG" --import $importFile

# 4. Set ultimate trust
gpg --homedir "C:\GNU\GnuPG" --edit-key <KEY_ID>
# At prompt: trust → 5 → quit

# 5. Verify
gpg --homedir "C:\GNU\GnuPG" --list-keys <KEY_ID>
```

---

## GPG Command Anatomy Reference

QPEC constructs GPG commands in this form:
```
gpg -r <RECIPIENT_KEY_ID> [-u <SIGNING_KEY_ID>] --homedir "C:\GNU\GnuPG" -es <file>
```

| Argument | Source | Purpose |
|----------|--------|---------|
| `-r <ID>` | QPTM trading partner config | Encrypt to this recipient (their public key) |
| `-u <ID>` | QPTM signing key config | Sign with this key (our private key) |
| `--homedir` | Hardcoded in QPEC | Always `C:\GNU\GnuPG` — shared by all accounts |
| `-es` | QPEC | Encrypt and sign |

The `--homedir` being hardcoded means: it doesn't matter which Windows account runs
the QPEC service — all accounts use the same keyring. Service account mismatch does
NOT cause GPG failures (it may cause other issues, but not the GPG errors above).

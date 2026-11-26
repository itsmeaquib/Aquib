# DB Refresh Patterns Reference

When a UAT database is refreshed from PRD, it overwrites QPTM configuration with
production values. This reference documents what changes, how to detect it, and
how to determine the correct UAT values.

---

## What a DB Refresh Overwrites

A DB refresh replaces the UAT QPTM database with a copy of PRD. This affects:

| Config Item | PRD Value (written by refresh) | UAT Correct Value |
|-------------|-------------------------------|-------------------|
| Signing key ID | PRD private key ID (e.g., `E66B8C0B`) | UAT private key ID (e.g., `F8F1C5B0`) |
| Trading partner recipient key IDs | PRD public key IDs | UAT/TEST key IDs (may differ per partner) |
| ISA06 sender ID | PRD sender qualifier | UAT sender qualifier |
| QPEC service account | PRD service account name | UAT service account |
| SFTP/AS2 connection strings | PRD endpoints | UAT endpoints |

---

## Detecting a DB Refresh as Root Cause

**Strong indicators:**
1. Failures began on a known DB refresh date (check change tickets in ADO)
2. ALL trading partners started failing simultaneously (not just one)
3. The signing key ID in the GPG error matches the PRD keyring, not UAT
4. ISA06 acknowledgment errors appear alongside encryption errors

**Confirm by comparing keyrings:**

Run on UAT server:
```powershell
gpg --homedir "C:\GNU\GnuPG" --list-secret-keys
gpg --homedir "C:\GNU\GnuPG" --list-keys
```

Run on PRD server (read-only — do not change PRD):
```powershell
gpg --homedir "C:\GNU\GnuPG" --list-secret-keys
gpg --homedir "C:\GNU\GnuPG" --list-keys
```

**If the signing key ID in the QPTM error matches the PRD secret key ID (not the
UAT secret key ID) → DB refresh is confirmed as the cause.**

---

## Comparison Checklist

Work through this for each application after a suspected DB refresh:

### 1. Signing Key
- [ ] List secret keys on UAT QPEC server → note the key ID (this is the correct UAT signing key)
- [ ] Check what key ID QPTM is configured to use (from segregated log `-u <KEY_ID>`)
- [ ] Do they match? If not → QPTM signing key ID needs updating

### 2. Trading Partner Recipient Keys

For each trading partner in the environment:
- [ ] Find their ADO setup ticket (search: `<partner name> QPEC UAT`)
- [ ] Note which key ID was imported to UAT at setup time
- [ ] Check if that key ID exists in the UAT keyring:
  ```powershell
  gpg --homedir "C:\GNU\GnuPG" --list-keys <KEY_ID>
  ```
- [ ] Check if QPTM references the same key ID (from segregated log `-r <KEY_ID>`)
- [ ] If QPTM now references a PRD key ID → it needs to be updated to the UAT key ID

**Note on TEST vs PROD keys:** Some trading partners maintain separate TEST and PROD
PGP keys. In UAT, QPTM should reference the TEST key. DB refresh replaces this with
the PROD key reference, and since the PROD key isn't in the UAT keyring, you get
Error Type B (`public key not found`).

### 3. ISA06 Sender ID
- [ ] Check QPTM config for ISA06 sender ID
- [ ] Compare with the value used in UAT before the refresh
- [ ] If PRD ISA06 value is present → update to UAT ISA06 value

### 4. Service Account
- [ ] Check `{SU}` in segregated logs — what is the actual Windows service account?
- [ ] Check `{AO}` in segregated logs — what does QPTM think the account should be?
- [ ] They should match and both should be the UAT service account
- [ ] If QPTM has the PRD account name configured → update to UAT account

---

## Finding the Correct UAT Values

**For signing key ID:**
The correct UAT signing key ID is whatever private key exists in the UAT keyring.
Run `--list-secret-keys` on the UAT server and use that key ID.

**For trading partner recipient key IDs:**
1. Search ADO for `<partner name> QPEC <environment>` — the setup ticket lists the key
2. Look at screenshots or comments in the setup WI — the key ID is usually explicit
3. If the partner has a TEST key, the WI attachment should be labeled accordingly

**For ISA06 sender ID:**
Check historical ADO requests, testing tickets, or ask the EDI team what ISA06 value
was used in UAT before the refresh.

**For service account:**
Check the ADO setup ticket for the environment or the QPEC service configuration
in Windows Services on the UAT server.

---

## QPTM Changes After DB Refresh — Typical Action List

After diagnosis, hand this list to the QPEC admin (Brannan or equivalent):

```
QPTM Changes Required for <Environment> after DB Refresh:

1. Update signing key ID: <PRD_KEY_ID> → <UAT_KEY_ID>

2. Update trading partner recipient keys:
   - <Partner A>: <PRD_KEY_ID> → <UAT_TEST_KEY_ID>
   - <Partner B>: <PRD_KEY_ID> → <UAT_TEST_KEY_ID>
   (Partners using the same key in UAT and PRD: no change needed)

3. Update ISA06 sender ID: <PRD_VALUE> → <UAT_VALUE>
   (if overwritten)

4. Update service account: <PRD_ACCOUNT> → <UAT_ACCOUNT>
   (if overwritten)

After changes:
- Restart QPEC service
- Trigger test transmission to each affected trading partner
- Confirm success in segregated logs
```

---

## PRD Key Export to UAT (Public Keys Only)

When a trading partner's public key needs to be added to UAT and it already exists
in the PRD keyring, you can export it safely:

```powershell
# On PRD server (read-only operation — safe)
gpg --homedir "C:\GNU\GnuPG" --armor --export <KEY_ID> > partner_key_exported.asc

# Transfer the file to UAT server
# CHECK FOR UTF-16 BOM BEFORE IMPORTING (see gpg-diagnostics.md)

# On UAT server
Get-Content .\partner_key_exported.asc -Encoding Byte | Select-Object -First 4
# If FF FE detected → convert: Get-Content .\file.asc | Set-Content -Encoding ASCII .\file_clean.asc

gpg --homedir "C:\GNU\GnuPG" --import .\partner_key_exported.asc
gpg --homedir "C:\GNU\GnuPG" --edit-key <KEY_ID>  # trust → 5 → quit
gpg --homedir "C:\GNU\GnuPG" --list-keys <KEY_ID>  # verify
```

**NEVER export private/signing keys from PRD to UAT.**

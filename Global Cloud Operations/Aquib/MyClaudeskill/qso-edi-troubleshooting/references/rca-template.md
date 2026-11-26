# RCA Document Template

Use this template when generating Root Cause Analysis documents for EDI incidents.
Fill in all sections. Paste log evidence verbatim — don't paraphrase it.

---

```markdown
# Root Cause Analysis — EDI Encryption Failure
## Incident: [ADO Ticket Number] | [Application Environment]
**Date:** [Date of RCA authorship]
**Author:** [Name/Team]
**Status:** [Draft / Final]

---

## 1. Incident Summary

| Field | Value |
|-------|-------|
| Incident ticket | [ADO/ServiceNow number] |
| Application | [e.g., HPE_HD_UATA1] |
| Environment | [UAT / PRD / DR] |
| First failure | [YYYY-MM-DD HH:MM:SS — from logs, not report time] |
| Reported at | [YYYY-MM-DD HH:MM] |
| Resolved at | [YYYY-MM-DD HH:MM — or "Pending"] |
| Duration | [X hours Y minutes] |
| Affected partners | [List all trading partners with failures] |
| Total failures | [Count of failed transmissions from logs] |
| Impact | [What was the business impact? Files stuck? 997s missing?] |

---

## 2. Root Cause

[One clear, specific statement of root cause. Example:]

"A DB refresh performed on [DATE] overwrote the QPTM configuration for [APPLICATION]
with production values. This caused two distinct GPG failures:
(1) The QPTM signing key ID was set to `[PRD_KEY_ID]`, which has no corresponding
private key in the UAT keyring — causing all outbound encryptions to fail with
'secret key not available'.
(2) Trading partner [PARTNER] is configured with recipient key ID `[KEY_ID]`, which
was never imported to the correct UAT QPEC server `[SERVER]` — causing those
specific transmissions to additionally fail with 'public key not found'."

---

## 3. Log Evidence

### Evidence A: [Error type description]

From `[log filename]`, [earliest/representative] failure at `[timestamp]`:

```
[Paste exact log entry here — include timestamp, {SU}/{AO} context,
GPG arguments line, and all error output lines]
```

### Evidence B: [If second error type present]

From `[log filename]`:

```
[Paste exact log entry here]
```

---

## 4. Timeline

| Time | Event |
|------|-------|
| [DATE TIME] | DB refresh performed (or other triggering change) |
| [DATE TIME] | First GPG failure recorded in logs |
| [DATE TIME] | Issue reported to EDI team / ticket created |
| [DATE TIME] | Investigation begun |
| [DATE TIME] | Root cause identified |
| [DATE TIME] | [Action taken — e.g., public key imported] |
| [DATE TIME] | [Action taken — e.g., QPTM signing key updated] |
| [DATE TIME] | QPEC service restarted and test transmission verified |
| [DATE TIME] | Incident resolved (or pending) |

---

## 5. Contributing Factors

List all factors that led to or amplified the impact:

- **[Primary]** [e.g., DB refresh overwrote UAT QPTM config with PRD values]
- **[Secondary]** [e.g., Key was previously imported to wrong QPEC server, so no
  UAT key existed on correct server when needed]
- **[Secondary]** [e.g., No automated alerting on GPG failures — issue went
  undetected for X hours after first failure]
- **[Secondary]** [e.g., UAT environment not tested after DB refresh per standard
  procedure]

---

## 6. Remediation

### Completed
- [ ] [Action completed — e.g., Imported trading partner public key `6B216B1D` to
  QCUHPEQPEC502 with ultimate trust set]
- [ ] [Action completed — e.g., Identified correct QPTM signing key ID for UAT]

### Pending
- [ ] **[Owner]** — [Action needed — e.g., Update QPTM signing key ID from
  `E66B8C0B` (PRD) to `F8F1C5B0` (UAT) in HPE_HD_UATA1 configuration]
- [ ] **[Owner]** — [Action needed — e.g., Update trading partner Destina recipient
  key from `B738C1B2` (PROD PGP) to `396652FC` (TEST PGP) in QPTM]
- [ ] **[Owner]** — Restart QPEC service on `[SERVER]` after config changes
- [ ] **[Owner]** — Trigger test transmission to each affected trading partner
  and confirm success in segregated logs

---

## 7. Prevention

Actions to prevent recurrence:

1. **Post-DB-refresh checklist** — Before declaring a DB refresh complete in UAT,
   verify: (a) signing key ID in QPTM matches UAT keyring, (b) all trading partner
   recipient key IDs reference UAT/TEST keys, (c) ISA06 sender ID is UAT value,
   (d) test transmission to at least one trading partner succeeds.

2. **Correct server verification** — When setting up a new trading partner in UAT,
   confirm which QPEC server hostname the target application instance runs on before
   importing keys.

3. **Post-import verification** — After every key import, trigger a test file to
   confirm encryption succeeds (don't just verify the import command output).

4. **Alerting** — Consider implementing monitoring on GPG error patterns in
   segregated logs to reduce detection time from hours to minutes.

---

## 8. ADO Fields (Copy-Paste Ready)

**Root Cause (1-2 sentences for ticket):**
[Brief root cause statement for the ADO ticket field]

**Resolution Notes:**
[Summary of what was done and what is pending]

**Lessons Learned:**
[Key takeaways for the team]
```

---

## Tips for a Strong RCA

1. **Use exact timestamps from logs**, not the report time. The first log entry with
   the error is the real start time.

2. **Paste log evidence verbatim.** Don't summarize the error — show the exact text.
   This makes the RCA verifiable and prevents future misinterpretation.

3. **Separate completed vs. pending remediation.** It's common for the RCA to be
   published while some fixes are still in progress.

4. **Name specific owners for pending items.** Vague "team to action" items don't get done.

5. **Count the failures.** "213 failed encryptions over 3 days" is more compelling
   and useful than "multiple failures."

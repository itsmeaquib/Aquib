---
name: cres-okta-triage-wkf-01
description: >
  Okta / SSO / Identity incident triage advisor for the GCO Cloud Resolution team.
  Advisory-only — reads tickets and logs, NEVER writes to ADO or modifies any system.
  Trigger on any of: "okta", "sso", "saml", "mfa", "identity", "federation", "authentication
  failed", "login loop", "certificate expired", "provisioning failed", "deprovisioning",
  "okta timeout", "okta error", "okta triage", "triage okta", "okta incident", "sso broken",
  "user can't log in", "okta push", "verify okta", "okta health check", or any phrase
  combining a customer name with login / auth / sso / okta. Also trigger when a work item
  number is provided alongside an Okta or SSO symptom description. Always use this skill
  proactively — even if the user just pastes an error message that looks auth-related.
compatibility:
  required_mcp: azure-devops, Microsoft 365
  optional_mcp: Salesforce Standard MCP
---

# CRES-OKTA-TRIAGE-WKF-01 — Okta / SSO Incident Triage Advisor

## ⚠️ Hard Rules (never violate)

1. **Read-only.** This skill NEVER writes to ADO tickets, never calls `wit_update_work_item`,
   never calls `wit_add_work_item_comment`, and never modifies any system. It produces advisory
   output only. The engineer reviews and posts manually.
2. **No speculation.** Every finding must trace to retrieved data (ticket, log, error text, or
   reference doc). If evidence is absent, say so explicitly.
3. **Draft-first.** All suggested responses, RCA notes, and resolution steps are clearly marked
   `[DRAFT — NOT POSTED]`.

---

## Overview

This skill triages Okta, SAML, MFA, and identity-federation incidents in the Quorum
`myQuorum Cloud` environment. It reads the ADO ticket and any supplied logs/error text,
classifies the failure pattern, matches known resolution paths, and produces a structured
advisory note ready for the engineer to review before posting.

**Primary contacts in your environment:**
- Okta escalations: Erik Vinson
- ADO org: `quorumsoftware`, project: `myQuorum Cloud`
- Tenant: `ce68f836`

---

## Workflow

### Step 1 — Collect Input

Accept any of:
- A bare ADO work item ID (e.g., `12345`)
- A work item ID + pasted error text or log excerpt
- Raw error text / log snippet only (no ticket)
- A customer name + symptom description

If a work item ID is provided, fetch it immediately:
```
wit_get_work_item(id=<ID>, project="myQuorum Cloud", expand="all")
wit_list_work_item_comments(workItemId=<ID>, project="myQuorum Cloud")
```

Extract from the ticket:
- Customer / org name
- Affected users (one, many, all)
- Error message(s) verbatim
- Timestamps of the reported event window
- Any attachment filenames (screenshots, HAR files, log files)
- Previous comments / resolution attempts

If attachments exist, fetch them:
```
wit_get_work_item_attachment(attachmentId=<id>, project="myQuorum Cloud")
```
Decode base64 → scan for error codes, SAML assertion snippets, HTTP status codes.

---

### Step 2 — Classify the Failure Pattern

Map the collected evidence to one of the **known Okta failure categories** below.
More than one may apply — list all matches.

| # | Category | Key Signals |
|---|----------|-------------|
| A | **SAML Certificate Expired / Mismatch** | `SAML2 Authn request failed`, cert thumbprint mismatch, `certificate has expired`, SP metadata out of date |
| B | **Okta App Assignment / Provisioning** | User not assigned to app, `User is not assigned`, `404` on SCIM endpoint, `UD0001`, group push failure |
| C | **MFA Challenge / Push Failure** | `MFA_ENROLL_REQUIRED`, `FACTOR_ENROLL_REQUIRED`, Okta Verify push timeout, `MFA_CHALLENGE` loop |
| D | **SSO Login Loop / Redirect Loop** | Browser redirect loop, `RelayState` mismatch, SP-initiated vs IdP-initiated mismatch, stale session cookie |
| E | **Network / Connectivity to Okta** | `ETIMEDOUT` to `*.okta.com`, DNS resolution failure, firewall blocking Okta IPs/ports |
| F | **AD / LDAP Sync Failure** | `PasswordPolicyViolation`, AD attribute sync error, `LOCKED_OUT`, account disabled in AD but active in Okta |
| G | **Token / Session Expiry** | `Token expired`, short session duration, `invalid_grant`, refresh token revoked |
| H | **Okta Org-Level / Admin Issue** | Rate limits, Okta org in read-only mode, admin API token expired, Workflows failure |
| I | **Deprovisioning / Access Removal** | User still active post-termination, group membership not reflecting AD change, SCIM deprovisioning stuck |
| J | **Unclassified / Unknown** | None of the above — flag for manual review |

Read the reference file for deeper pattern-matching guidance:
→ `references/okta-patterns.md`

---

### Step 3 — Resolution Path

For each matched category, emit the corresponding resolution steps from the table below.
Adapt to the specific evidence (customer, error text, timestamps).

#### A — SAML Certificate Expired / Mismatch
1. Log in to Okta Admin Console → Applications → [App Name] → Sign On tab.
2. Verify the active SAML certificate expiry date. If expired: **Generate new certificate** (do not activate yet).
3. Export the new certificate metadata XML / fingerprint.
4. Update the SP side (IIS app, Quorum application config, or customer IdP) with the new cert metadata.
5. Activate the new certificate in Okta only after SP-side update is confirmed.
6. Test SP-initiated and IdP-initiated login.
7. **Escalate to Erik Vinson** if cert rotation requires customer coordination or if the SP is customer-managed.

#### B — App Assignment / Provisioning
1. Okta Admin → People → [User] → Applications tab — confirm assignment to the app.
2. If missing: Assign via group or direct assignment. Check group rules if group-based.
3. If SCIM: Applications → [App] → Provisioning → check import/push logs for the specific error code.
4. For `UD0001`: verify attribute mapping — usually a required attribute (email, username) is blank.
5. Re-push user profile after fixing mapping. Verify in the target app.
6. If bulk: export affected users list from ticket, fix group membership in AD (which syncs to Okta via LDAP).

#### C — MFA Challenge / Push Failure
1. Confirm whether the user ever enrolled a factor (Okta Admin → People → [User] → Security tab).
2. If not enrolled: reset MFA enrollment for the user → have them re-enroll on next login.
3. If push timeout: check Okta Verify app version on user's device. Outdated versions drop push silently.
4. If `MFA_ENROLL_REQUIRED` org-wide for new users: verify the enrollment policy assignments.
5. Temporary bypass (if urgent): Okta Admin → People → [User] → Reset MFA (confirm with manager before doing this).
6. Document bypass clearly in ticket comment before applying.

#### D — SSO Login Loop / Redirect Loop
1. Clear browser cookies/cache for the SP domain and `*.okta.com` — test in incognito.
2. Verify `RelayState` and `ACS URL` in Okta app settings match exactly what the SP sends.
3. Check whether SP is sending SP-initiated vs IdP-initiated — confirm the app's `SSO URL` in Okta matches the SP's assertion consumer service URL.
4. In IIS apps: check the application's SAML module config (`web.config` or SAML middleware) for mismatched entity IDs.
5. If intermittent: suspect stale session — Okta Admin → Sessions → revoke user session → retest.
6. Capture a HAR file if loop persists and attach to ADO ticket for deeper analysis.

#### E — Network / Connectivity to Okta
1. From the affected server/VM, test: `Test-NetConnection -ComputerName <customer>.okta.com -Port 443`
2. Also test: `Resolve-DnsName <customer>.okta.com`
3. If blocked: escalate to network/firewall team with required Okta IP ranges:
   - Okta publishes their IP ranges at: https://help.okta.com/en-us/content/topics/security/ip-address-allow-listing.htm
4. If DNS fails: verify internal DNS forwarders are resolving external `okta.com` correctly.
5. Proxy environments: confirm the app server has the Okta HTTPS endpoint in its proxy bypass list.
6. Arc-connected servers: pull event logs via `azure-event-logs` skill to check for Schannel/TLS errors alongside the connectivity failure.

#### F — AD / LDAP Sync Failure
1. Okta Admin → Directory → Active Directory → [Domain] → check last sync time and error count.
2. Identify the specific user's AD account: confirm account is enabled, not locked, not expired.
3. If `LOCKED_OUT`: unlock in AD → wait for next Okta sync cycle (or force sync via Okta Admin).
4. If attribute mismatch: correct the AD attribute (UPN, email, `sAMAccountName`) → re-sync.
5. Check Okta AD agent health: Okta Admin → Directory → AD → Agents tab — agent must show "Connected".
6. If agent offline: restart the Okta AD Agent service on the agent server → verify reconnect.

#### G — Token / Session Expiry
1. Confirm the session policy: Okta Admin → Security → Global Session Policy — check `Maximum Session Lifetime`.
2. If too short for the application's use case, adjust session policy (confirm with customer before changing).
3. For `invalid_grant` on refresh token: check the app's OAuth settings — `Refresh Token` grant type must be enabled.
4. Token clock skew: verify server time is synced (NTP). Skew > 5 min causes JWT validation failures.
5. Force user to re-authenticate fresh: Okta Admin → People → [User] → Sessions → Revoke All Sessions.

#### H — Okta Org-Level / Admin Issue
1. Check Okta Status Page: https://status.okta.com — confirm no active incident for the customer's cell.
2. If admin API token expired: Okta Admin → Security → API → Tokens — rotate the expired token and update any integrations using it.
3. Rate limits: review Okta System Log for `429` errors. If hit, identify the source (Okta Workflows, SCIM, API calls) and throttle/batch.
4. Okta Workflows: Okta Admin → Workflows Console → check failed flow runs for the relevant workflow.
5. **Escalate to Erik Vinson** for org-level admin changes or rate limit exceptions.

#### I — Deprovisioning / Access Removal
1. Verify AD account status for the terminated user: should be disabled in AD.
2. Check Okta profile: if still active after AD disable, check Okta AD Agent sync lag (force sync if needed).
3. SCIM deprovisioning: Applications → [App] → Provisioning → check for stuck deprovisioning tasks.
4. Manually deactivate in Okta if sync is stuck: People → [User] → Deactivate (log this action in ADO ticket).
5. Verify all assigned apps show "Not Assigned" after deactivation.
6. If access was to a sensitive system: flag for security review before closing ticket.

#### J — Unclassified
- Collect verbatim error messages, Okta System Log event IDs, and timestamps.
- Pull Okta System Log export if available (customer or Erik Vinson can pull via Admin Console → Reports → System Log).
- Escalate to Erik Vinson with all collected evidence.

---

### Step 4 — Okta System Log Analysis (if log data is provided)

If the user pastes Okta System Log entries or an exported log file, parse the following fields:

| Field | What to look for |
|-------|-----------------|
| `eventType` | `user.authentication.auth_via_mfa`, `user.session.start`, `policy.evaluate_sign_on`, `user.account.lock` |
| `outcome.result` | `FAILURE`, `DENY`, `CHALLENGE` |
| `outcome.reason` | Specific failure reason — map to category table above |
| `debugContext.debugData` | `requestId`, `dtHash`, SAML assertion snippets |
| `actor.displayName` | Who triggered the event |
| `target[].displayName` | Which app or user was targeted |
| `client.ipAddress` | Source IP — flag unexpected geos |
| `published` | Timestamp — correlate to the customer's reported event window |

Group events by `actor` and `outcome.result=FAILURE`, sort by timestamp, and produce a **failure timeline**.

---

### Step 5 — Escalation Decision

Escalate to **Erik Vinson** when any of the following are true:
- Certificate rotation requires customer coordination
- Org-level admin changes are required (session policies, rate limits, app settings affecting all users)
- The failure is unclassified after full triage (Category J)
- SCIM deprovisioning is stuck and a sensitive system is involved
- The issue has been unresolved > 4 hours and affects multiple users
- The Okta System Log shows `DENY` from a policy the engineer cannot modify

Escalation note template (fill and present to engineer — **do not post**):

```
[DRAFT — NOT POSTED]

Escalation to: Erik Vinson (Okta Admin)
Ticket: #<ID> — <Title>
Customer: <Customer Name>
Reported: <Timestamp>
Failure Category: <A/B/C/.../J>
Error: <verbatim error message>
Steps Already Taken: <list>
Reason for Escalation: <specific reason from list above>
Recommended Action: <what Erik needs to do>
```

---

### Step 6 — Output Format

Emit the following advisory block in the chat. **Never post to ADO.**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OKTA TRIAGE ADVISORY  [DRAFT — NOT POSTED]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket       : #<ID> — <Title>
Customer     : <Name>
Reported     : <Timestamp>
Affected     : <scope: single user / multiple users / all users>

FAILURE CATEGORY
  [X] A — SAML Certificate        [ ] B — App Assignment
  [ ] C — MFA / Push              [ ] D — Login Loop
  [ ] E — Network/Connectivity    [ ] F — AD Sync
  [ ] G — Token/Session           [ ] H — Org-Level Admin
  [ ] I — Deprovisioning          [ ] J — Unclassified

ROOT CAUSE (evidence-based)
  <1–3 sentences traceable to ticket/log data>

RESOLUTION STEPS
  1. <step>
  2. <step>
  ...

ESCALATE TO ERIK VINSON?  Yes / No
  Reason: <if Yes>

SUGGESTED ADO COMMENT (review before posting)
─────────────────────────────────────────────
<Ready-to-post plain-text comment. Professional tone.
 No markdown. Summarises triage, steps taken/recommended,
 and next owner.>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### Step 7 — PowerShell Verification Snippets

Where applicable, emit a PowerShell block the engineer can run against the affected server
to gather evidence before/after remediation.

**Check Okta AD Agent service status:**
```powershell
# WARNING: Read-only check. Run on the Okta AD Agent host server.
Get-Service -Name "Okta AD Agent*" | Select-Object Name, Status, StartType
```

**Test connectivity to Okta endpoints:**
```powershell
# WARNING: Read-only. Run from the affected server or jump host.
$oktaDomain = "<customer>.okta.com"
Test-NetConnection -ComputerName $oktaDomain -Port 443 -InformationLevel Detailed
Resolve-DnsName $oktaDomain
```

**Check server time sync (clock skew causes JWT failures):**
```powershell
# WARNING: Read-only.
w32tm /query /status
(Get-Date).ToUniversalTime()
```

**Check for Schannel / TLS errors in Windows event log (IIS/app server):**
```powershell
# WARNING: Read-only. Pulls last 50 Schannel errors.
Get-WinEvent -LogName "System" -MaxEvents 200 |
  Where-Object { $_.ProviderName -eq "Schannel" -and $_.LevelDisplayName -in "Error","Warning" } |
  Select-Object TimeCreated, Id, Message |
  Sort-Object TimeCreated -Descending |
  Select-Object -First 50 |
  Format-Table -AutoSize -Wrap
```

> ⚠️ **Production Risk:** All snippets above are read-only queries. None modify system state.
> Run in a non-interactive terminal session on the appropriate server. Confirm server name
> before executing.

---

## Quick-Reference Okta Error Codes

| Code | Meaning | Typical Fix |
|------|---------|-------------|
| `E0000068` | Invalid token provided | Rotate API token |
| `E0000095` | Operation not allowed on the current user status | Activate/reactivate user first |
| `E0000047` | API call exceeded rate limit | Throttle API calls / check Workflows |
| `E0000011` | Invalid token, token has expired | Re-authenticate / reissue token |
| `E0000001` | API validation failed | Check request payload against Okta API spec |
| `UD0001` | A required attribute is missing | Fix attribute mapping in Okta provisioning |
| `UD0003` | The value of the attribute is already in use | Duplicate username/email in target app |
| `MFA_ENROLL_REQUIRED` | User must enroll MFA | Enroll or reset factor |
| `FACTOR_ENROLL_REQUIRED` | Factor not enrolled | Same as above |
| `ACCOUNT_LOCKED_OUT` | Okta account locked | Unlock via Admin Console or AD sync |
| `PASSWORD_EXPIRED` | Password expired in Okta or synced AD | Reset in AD; wait for sync or force |

---

## Reference Files

- `references/okta-patterns.md` — Deep-dive pattern matching for ambiguous log entries,
  SAML assertion debugging, and HAR file analysis guidance.

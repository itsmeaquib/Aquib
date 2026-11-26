# Okta Pattern Reference — Deep-Dive Guide

## Table of Contents
1. [SAML Assertion Debugging](#saml-assertion-debugging)
2. [Ambiguous Log Entry Patterns](#ambiguous-log-entry-patterns)
3. [HAR File Analysis](#har-file-analysis)
4. [Okta System Log — Key Event Types](#okta-system-log--key-event-types)
5. [Common Quorum Environment Notes](#common-quorum-environment-notes)

---

## SAML Assertion Debugging

When a SAML failure is suspected but the error is vague (e.g., "login failed", blank page,
redirect loop), follow this checklist:

### Decode the SAML Response
If you have the raw SAML response (from HAR file, browser DevTools → Network → POST to ACS URL):
1. Extract the `SAMLResponse` parameter value from the POST body.
2. Base64-decode it → you get an XML document.
3. Check the following fields in the XML:

| XML Path | What to validate |
|----------|-----------------|
| `<saml:Issuer>` | Must match the Entity ID configured in the SP |
| `<ds:X509Certificate>` | Must match the cert currently active in Okta |
| `<saml:Conditions NotBefore NotOnOrAfter>` | Must be within current UTC time ± 5 min |
| `<saml:NameID>` | Must match the username format the SP expects (email vs UPN vs sAMAccountName) |
| `<saml:Attribute Name="...">` | Required attributes must be present and non-empty |
| `<ds:Signature>` | Must validate against the active Okta cert |

**PowerShell — decode SAML response from clipboard:**
```powershell
# Paste the raw SAMLResponse value into a variable
$encoded = "<paste base64 here>"
$decoded = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($encoded))
$decoded | Out-File "$env:TEMP\saml_response.xml" -Encoding UTF8
notepad "$env:TEMP\saml_response.xml"
```

### Common SAML Mismatch Scenarios

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| SP says "Issuer not recognized" | Entity ID in Okta doesn't match SP's expected issuer | Update Okta app's Audience URI / Entity ID |
| "Certificate validation failed" | Old cert fingerprint in SP config | Re-export new cert from Okta → update SP |
| Assertion expired | Server clock skew > 5 min, or assertion lifetime too short | Sync NTP; or extend `NotOnOrAfter` in Okta session settings |
| `NameID` format mismatch | Okta sends email, SP expects Windows domain\\user | Change NameID format in Okta app Sign On → Advanced settings |
| Missing required attribute | Attribute not mapped in Okta app profile mapping | Add attribute mapping in Okta app → Provisioning → Attribute Mappings |

---

## Ambiguous Log Entry Patterns

These Okta System Log patterns are frequently misclassified:

### Pattern: `policy.evaluate_sign_on` → `DENY`
- **Not always** a user error. Could be IP zone restriction, device trust policy, or network zone.
- Check: `debugContext.debugData.behaviors` — lists which risk signals triggered DENY.
- Check: `debugContext.debugData.requestId` — pull the full event chain for this requestId.
- Common cause in Quorum env: user connecting from a new IP (VPN change, home network shift)
  after an IP allowlist policy was tightened.

### Pattern: `user.session.start` → `FAILURE` immediately after `SUCCESS`
- Indicates session was created then immediately revoked.
- Usually: concurrent session limit hit, or a Workflow terminated the session.
- Check: Okta Admin → Security → Global Session Policy → "Maximum concurrent sessions".
- Check: Okta Admin → Workflows Console for any session-terminating flows triggered on login.

### Pattern: `system.agent.ad.operation.failed` 
- AD Agent operation failure — NOT always a user-facing issue, but precedes sync breakdowns.
- Sub-codes to watch: `AGENT_CONNECTIVITY_ISSUE`, `AGENT_ERROR_LDAP_CONN`.
- Resolution: restart Okta AD Agent service on agent server; verify LDAP port 389/636 is reachable.

### Pattern: `app.oauth2.token.grant.implicit` → `FAILURE`
- Implicit flow is deprecated in Okta. SP may be using an outdated OAuth flow.
- Fix: change SP OAuth grant type to `Authorization Code + PKCE`. Confirm with app owner.

### Pattern: `user.lifecycle.deactivate` with actor = `System`
- User was auto-deactivated by Okta lifecycle policy (e.g., inactivity rule after N days).
- This is often unexpected for customers. Reactivate: People → [User] → Activate.
- Advise customer to review inactivity deactivation policy if unintentional.

---

## HAR File Analysis

When a customer provides a `.har` file (browser network trace), follow this sequence:

1. Open HAR file in a text editor or JSON viewer (it's JSON format).
2. Search for requests to `*.okta.com` — focus on:
   - `POST` to `/app/<app>/sso/saml` — SP-initiated SAML start
   - `POST` to `<customer>.okta.com/login/sessionCookieRedirect` — session redirect
   - `POST` to ACS URL (SP side) — final SAML assertion delivery
3. For each relevant request, check:
   - HTTP status code (expect 200 or 302; anything else is a signal)
   - Response headers: `Location` (on redirects), `Set-Cookie` (session cookie being set?)
   - Request body: `SAMLResponse`, `RelayState` values (decode SAMLResponse per section above)
4. Look for **redirect loops**: the same URL appearing 3+ times in sequence = loop.
5. Look for **broken redirect**: `Location` header pointing to localhost or an internal IP = misconfigured ACS URL.

---

## Okta System Log — Key Event Types

Quick reference for the most useful event types when filtering Okta System Log exports:

| eventType | Meaning |
|-----------|---------|
| `user.authentication.auth_via_mfa` | MFA authentication attempt |
| `user.authentication.sso` | SSO authentication |
| `user.session.start` | Session created |
| `user.session.end` | Session ended |
| `user.account.lock` | Account locked |
| `user.account.unlock_by_admin` | Admin unlocked account |
| `user.lifecycle.activate` | User activated |
| `user.lifecycle.deactivate` | User deactivated |
| `user.lifecycle.suspended` | User suspended |
| `policy.evaluate_sign_on` | Sign-on policy evaluated |
| `app.user_management.push_profile_failure` | SCIM push failure |
| `app.user_management.push_new_user` | SCIM user push attempt |
| `system.agent.ad.operation.failed` | AD Agent operation failed |
| `app.inbound_del_auth.login_failure` | Inbound delegated auth failure |
| `application.lifecycle.update` | App config changed |

**Useful OCSQL-style filter for failures only (if exporting via API):**
```
filter=outcome.result eq "FAILURE" and published gt "2025-01-01T00:00:00.000Z"
```

---

## Common Quorum Environment Notes

- **Okta escalation contact:** Erik Vinson. Loop in for any org-level change, cert rotation
  requiring customer coordination, or unresolved issues > 4 hours.
- **AD integration:** Quorum environments typically use Okta AD Agent for user sync from
  Active Directory. AD is the source of truth for user accounts; Okta mirrors it.
- **SAML apps in scope:** Citrix DaaS (Citrix FAS + SAML), myQuorum web apps, TIPS eweb,
  FlowCal web interfaces (where SSO is enabled). Each may have separate cert configs.
- **HMAC / eweb note:** TIPS eweb 400 errors can be HMAC-related, not Okta. Confirm whether
  the 400 happens before or after the Okta authentication step. If before → HMAC
  (`DESIGN_STUDIO|EnvironmentHMACSecret`). If after (post-SSO) → likely Okta attribute/session.
- **Citrix + Okta intersection:** Citrix VDA unregistration sometimes coincides with Okta
  session expiry on the Citrix StoreFront. If users get disconnected at a predictable interval,
  check StoreFront session timeout vs Okta session lifetime — they must align.
- **Tenant:** `ce68f836` (Azure AD / Entra ID backing tenant for Okta federation where applicable).

# Learned Cases

Real Integration Platform tickets that have been worked and captured. Read this file **first** on every case and compare each fingerprint with the error and flow in front of you. These entries sit alongside the wiki-based catalog and are often more specific. If one contradicts the catalog, show both and ask which is current.

Last updated: 2026-11-03 (no cases captured yet)

## How entries are written

- **Confirmed** means there is evidence the fix worked: events succeeded after the change, or the requestor validated. Use the entry as the answer, citing the ticket ID.
- **Hypothesis** means the cause is plausible but unproven. Use it only as a hint and still verify.
- The **fingerprint** is the exact error prefix plus the distinctive words. Keep it short so matching works.
- Never store secrets (client secrets, tokens, passwords, connection strings).
- Newest entries go at the top. Update an existing entry (add the ticket ID, raise Seen count, refine the resolution) rather than adding a near-duplicate.

## Entry template

```
### LC-NNN · <short title>
- **Status**: Confirmed | Hypothesis
- **Tickets**: <ADO IDs>  ·  **First seen**: <date>  ·  **Last seen**: <date>  ·  **Seen count**: <n>
- **Environment**: <IPCH or IPOP, QCloud or on-premises, version if known>
- **Flow**: <source product → target product>  ·  **Event type**: <e.g. quorum-business.event.flowcal.meter-updated>
- **Fingerprint**: <error prefix + distinctive text>
- **Symptoms**: <what the engineer sees in the UI and logs>
- **Root cause**: <cause> (Category <n> – <name>)
- **Evidence**: <what proved it>
- **Resolution**: <numbered steps, and who acts>
- **Republish**: <yes / no / after X>
- **Ruled out**: <what was checked and excluded>
- **Notes**: <version dependence, caveats, related wiki page or work item>
```

## Cases

*(none yet)*

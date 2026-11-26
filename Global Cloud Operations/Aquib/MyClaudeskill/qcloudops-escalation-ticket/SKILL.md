---
name: qcloudops-escalation-ticket
description: >
  Handles the full QCloudOps ticket escalation workflow in Azure DevOps (project: myQuorum Cloud).
  Use this skill whenever the user says "escalate ticket", "create escalation for", "run escalation
  prompt for", or "escalate #XXXXXXX to [team]". This skill fetches the parent ticket, prompts for
  the receiving team, builds a full draft escalation ticket (title, description, comment, all fields),
  waits for explicit user confirmation, then creates the ticket in ADO with a linked comment. Never
  skip steps or create tickets without confirmation. Always follow the exact 5-step flow below.
---

# QCloudOps Escalation Ticket Skill

Automates end-to-end ticket escalation from QCloudOps to internal
teams in Azure DevOps (project: **myQuorum Cloud**).

---

## Trigger Phrases
Any of the following should start this flow:
- "Escalate ticket #XXXXXXX"
- "Create escalation for #XXXXXXX"
- "Run escalation prompt for #XXXXXXX"
- "Escalate #XXXXXXX to [team]"

---

## STEP 1 — FETCH THE TICKET

When a ticket number is provided:
1. Fetch the work item from Azure DevOps (project: `myQuorum Cloud`)
2. Fetch all comments/discussion entries from the ticket
3. Do **not** ask the user for anything else — proceed immediately to Step 2

---

## STEP 2 — ASK FOR ESCALATION TEAM

Show the user this prompt and ask which team to escalate to:

> Which team should this be escalated to?
> - **Data Services** → Area Path: `myQuorum Cloud\Data Services`
> - **Infra Team** → Area Path: `myQuorum Cloud\QCloud and IT Infra Support`
> - **DevOps Team** → Area Path: `myQuorum Cloud\Global Cloud Operations`

Wait for the user's selection before continuing.

---

## STEP 3 — PREPARE AND SHOW DRAFT (DO NOT CREATE YET)

Once the team is selected, build the full draft and display it clearly. **Do not create the ticket yet.**

### TITLE
```
[Original Title] – Escalated to [Team Name]
```

### DESCRIPTION
Copy the **exact** description from the parent ticket.
Do NOT summarize, rephrase, or modify anything.

### DISCUSSION / COMMENT
Build an escalation summary using the ticket's comments:

```
🔁 ESCALATION SUMMARY — From QCloudOps to [Team Name]
Parent Ticket: #[TICKET NUMBER]

Investigation Done:
- [What was checked/investigated — derived from comments]

Steps Taken:
- [What was tried and the outcome — derived from comments]

Escalation Reason:
[Why this cannot be resolved by GCOC — what is blocking]

Action Required from [Team Name]:
[Specific actions needed from the receiving team]
```

### OTHER FIELDS (copy from parent ticket)
| Field | Value |
|---|---|
| AREA PATH | Based on team selected (see Step 2) |
| PRIORITY | Same as parent |
| CUSTOMER | Same as parent |
| ENVIRONMENT | Same as parent |
| PRODUCT | Same as parent |
| SEGMENT | Same as parent |
| PRODUCT FAMILY | Same as parent |
| CLOUD | Same as parent |
| OUTAGE | Same as parent |
| CLOUD PLATFORM | Same as parent |
| GLOBAL CLOUD TRIAGE | Same as parent |
| TAGS | `Escalated; [Team Name]; [Product]` |
| LINKED TO | Parent #[TICKET NUMBER] (Related) |
| ASSIGNED TO | Leave blank |

---

## STEP 4 — WAIT FOR CONFIRMATION

After showing the full draft, always say:

> "Please review the draft above. Reply **CONFIRM** to create the ticket, or let me know what to change."

**Do NOT create the ticket until the user replies with "confirm" (case-insensitive).**
If the user requests changes, update the draft and show it again before asking for confirmation again.

---

## STEP 5 — CREATE THE TICKET

Only after receiving "confirm":

1. Create the work item in ADO with all fields listed in Step 3
2. Add the escalation summary block as a **Discussion comment** on the new ticket
3. Link the new ticket to the parent ticket as **"Related"**
4. Reply with:
   - The new ticket number
   - A direct link to open it in ADO

---

## REQUIRED FIELDS FOR TICKET CREATION

These fields are mandatory — always copy from the parent to avoid validation errors:

| ADO Field Name | Notes |
|---|---|
| `System.AreaPath` | Set based on team selection |
| `System.IterationPath` | Copy from parent |
| `Custom.Outage` | Copy from parent |
| `Custom.Cloud` | Copy from parent |
| `Custom.Priority2` | Copy from parent |
| `Custom.CloudPlatform` | Copy from parent |
| `Custom.GlobalCloudTriage` | Copy from parent |
| `Custom.Segment` | Copy from parent |
| `Custom.ProductFamily` | Copy from parent |
| `QuorumCMMI.Customer` | Copy from parent |

---

## IMPORTANT RULES

- **Never** create a ticket without explicit user confirmation ("confirm")
- **Never** summarize or paraphrase the parent description — copy it verbatim
- If any required fields are missing from the parent ticket, flag them to the user before confirming
- If the user asks to change something in the draft, regenerate the full draft and re-ask for confirmation
- The escalation comment must always be added as a **Discussion entry**, not embedded in the description

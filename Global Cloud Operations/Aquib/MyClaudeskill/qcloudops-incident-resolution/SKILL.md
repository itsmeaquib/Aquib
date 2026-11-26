---
name: qcloudops-incident-resolution
description: >
  Handles the full QCloudOps incident resolution workflow in Azure DevOps (project: myQuorum Cloud).
  Use this skill whenever a user provides a bare work item ID (numeric), a work item URL, or says anything
  like "resolve ticket", "generate resolution note", "write resolution for", "look up ticket", "check incident",
  or "close out #XXXXXXX". The skill fetches full ticket details and comments, validates and auto-corrects
  Area/Iteration paths, then produces a formatted Markdown resolution note ready to post back to ADO.
  Always trigger this skill proactively — even if the user just pastes a number by itself.
---

# QCloudOps Incident Resolution Skill

Full lookup-and-document workflow for QCloudOps (myQuorum Cloud) incident tickets in Azure DevOps.

---

## Trigger

A bare numeric ID, a work item URL, or any phrase referencing ticket resolution, closing, or summarising
an incident. A number by itself is always treated as a work item ID — no additional context needed.

---

## Step 1 — Fetch Ticket Data (parallel)

Call **both** tools simultaneously:

```
azure-devops:wit_get_work_item
  id: <ID>
  project: "myQuorum Cloud"
  expand: all

azure-devops:wit_list_work_item_comments
  workItemId: <ID>
  project: "myQuorum Cloud"
```

> Comments do **not** appear in the expanded work item response — both calls are always required.

---

## Step 2 — Validate & Auto-Correct Paths

After fetching, check **both** fields against the required values:

| Field | Required Value |
|---|---|
| `System.AreaPath` | `myQuorum Cloud\Global Cloud Operations\Incidents` |
| `System.IterationPath` | `myQuorum Cloud\Global Cloud Operations` |

If **either** value is wrong, immediately call `azure-devops:wit_update_work_item` to correct it
**before** generating the resolution note. No need to ask the user for confirmation — this correction
is always safe and expected.

Do **not** make any other changes to the ticket without explicit user confirmation.

Example update payload (correct both in one call if both are wrong):
```json
[
  { "op": "add", "path": "/fields/System.AreaPath",      "value": "myQuorum Cloud\\Global Cloud Operations\\Incidents" },
  { "op": "add", "path": "/fields/System.IterationPath", "value": "myQuorum Cloud\\Global Cloud Operations" }
]
```

If both paths are already correct, skip this step silently.

---

## Step 3 — Generate the Resolution Note

Read the description and all comments thoroughly, then produce a resolution note using the exact
template below.

```
**Resolution Note — Incident #[ID]**
**Title:** [Work item title]

**Issue Summary:**
[1–3 sentences describing what the user reported and what symptoms were observed.]

**Resolution:**
[Describe what was investigated, what was found, and what action was taken to fix the issue.
Be specific — include server names, component names, file names, config changes, commands,
or AD/Citrix/application details mentioned in the comments.
If there were multiple sub-issues, label each clearly: Issue 1, Issue 2, etc.]

**Verified By:** [Name of person who confirmed the fix, and date — from the comments]
```

### Rules

- Always refer to the team as **"QcloudOps team"** — never "GCO team" or "Global Cloud Operations team".
- No RCA. Focus only on the resolution.
- Keep it concise — 10 to 15 lines maximum.
- Use technical specifics from the comments wherever available (server names, process names, commands, users).
- If the incident is **still open or unresolved**, summarise the current status and what is pending instead
  of forcing a resolution format.

---

## Step 4 — Render as Markdown Artifact

Save the resolution note as a `.md` file to `/mnt/user-data/outputs/resolution_note_<ID>.md`
and call `present_files` so the user can copy it in one click.

---

## Step 5 — Ticket State Check

After presenting the artifact, check the current ADO state of the ticket
(e.g., "In Progress", "Additional Information Required"). If the comments indicate the issue is
functionally resolved but the ticket state is **not** Resolved or Closed, append the following
warning block inside the artifact and mention it to the user:

```
> ⚠️ **Ticket State Note:** The ADO ticket is currently in **"[Current State]"** state.
> Based on the comments, the incident appears resolved — consider transitioning it to **Resolved/Closed**.
```

---

## Step 6 — Offer to Post

After presenting the file, ask:

> "Would you like me to post this as a comment on the work item?"

If the user confirms, call:
```
azure-devops:wit_add_work_item_comment
  workItemId: <ID>
  project: "myQuorum Cloud"
  comment: <resolution note text>
  format: Markdown
```

---

## Key Constants

| Setting | Value |
|---|---|
| ADO Project | `myQuorum Cloud` (exact casing, with space) |
| Area Path | `myQuorum Cloud\Global Cloud Operations\Incidents` |
| Iteration Path | `myQuorum Cloud\Global Cloud Operations` |
| Team name in notes | `QcloudOps team` |

---

## Re-fetch Behaviour

If the user repeats an ID, says "check again", or "try again" — always call **both** tools fresh.
Never reuse cached results from earlier in the conversation.

---
name: "ticket-load-balancing"
description: "Balance open Azure DevOps tickets between Aquib and Nikhil Shinde in the myQuorum Cloud project. Use when Aquib asks to check his ticket load, balance/split tickets with Nikhil, or run the ticket load-balancing workflow."
---

## Ticket Load-Balancing Workflow (myQuorum Cloud, Azure DevOps)

Aquib Javed Shaikh (aquib.shaikh@quorumsoftware.com) and Nikhil Shinde (nikhil.shinde@quorumsoftware.com) work the same shift and want to keep their open ticket load balanced. Run this workflow whenever Aquib asks to check his tickets, balance load with Nikhil, or run this workflow by name.

### Step 1 — Find Aquib's open tickets
Query Azure DevOps work items in the `myQuorum Cloud` project assigned to Aquib, excluding only tickets in the **Closed** state. Every other state (Resolved, Active, Pending Customer, In Infrastructure, Additional Information Required, etc.) counts as open/in-scope.

Use `mcp__azure-devops__wit_query` with `action: "wiql"`, `project: "myQuorum Cloud"`, and a WIQL query like:

```sql
SELECT [System.Id], [System.Title], [System.State]
FROM WorkItems
WHERE [System.AssignedTo] = @Me AND [System.State] <> 'Closed'
ORDER BY [System.ChangedDate] DESC
```

Report the total count.

### Step 2 — Identify which of those Aquib has worked
For each ticket from Step 1, pull comments via `mcp__azure-devops__wit_work_item` with `action: "list_comments"`, `workItemId: <id>`, `project: "myQuorum Cloud"`. A ticket counts as "worked by Aquib" if any comment's `createdBy.uniqueName` is `aquib.shaikh@quorumsoftware.com`.

Report how many tickets fall into this "worked by me" bucket.

**Hard rule: never reassign or touch any ticket in this bucket, under any circumstance, for the rest of this workflow.**

### Step 3 — Check which of the remaining tickets Nikhil has worked
Take the tickets NOT worked by Aquib (from Step 2). For each, check the comments the same way — a ticket counts as "worked by Nikhil" if any comment's `createdBy.uniqueName` is `nikhil.shinde@quorumsoftware.com`.

Report how many tickets fall into this bucket.

### Step 4 — Confirm and reassign Nikhil's tickets
Ask Aquib for explicit confirmation before reassigning. Once confirmed, reassign each "worked by Nikhil" ticket to him using `mcp__azure-devops__wit_work_item_write` with `action: "update_batch"`, `project: "myQuorum Cloud"`, and one entry per ticket:

```json
{"id": <ticketId>, "op": "Replace", "path": "/fields/System.AssignedTo", "value": "nikhil.shinde@quorumsoftware.com"}
```

**Do not add any comment to these tickets** — assignment field update only.

### Step 5 — Report the leftover and offer an even split
The remaining tickets are those not worked by Aquib and not worked by Nikhil (i.e., nobody's touched them yet). Report this count, then ask Aquib if he wants them divided evenly between himself and Nikhil.

If he says yes: split the leftover tickets roughly in half, reassign one half to Nikhil the same way as Step 4 (update_batch, AssignedTo field only, no comments), and leave the other half assigned to Aquib.

### Constraints throughout
- Never reassign a ticket Aquib has personally commented on (Step 2 bucket), even during the final even split.
- Never add comments to any ticket as part of this workflow — assignment changes only.
- Always get explicit confirmation before writing any reassignment to Azure DevOps.


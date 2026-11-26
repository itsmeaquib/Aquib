---
name: cres-catalog-reg-wkf-01
description: Registers Claude skills into the Quorum GCO AI Agent & Automation Catalog Excel file following the team naming convention. Use this skill whenever a user wants to add their skills to the catalog, comply skills with the GCO naming convention, register skills in the Excel sheet, update the catalog with new workflows, or asks anything like "add my skills to the catalog", "register my skills", "comply my skills with the naming convention", "fill the catalog sheet", or "catalog my skills". Always trigger this skill proactively when an Excel catalog file is uploaded alongside a request to register or add skills.
---

# GCO AI Agent Catalog — Skill Registration Workflow

Registers a user's Claude skills into the **Quorum GCO AI Agent & Automation Catalog** Excel file, following the official GCO naming convention and security gate rules.

---

## What This Skill Does

1. Reads the user's installed skills from `/mnt/skills/user/`
2. Proposes compliant names in the format `[DEPT]-[FUNCTION]-[TYPE]-[##]`
3. Renames the skill folders on disk
4. Asks the user to confirm the Phase for each skill
5. Derives the Security Gate automatically from the Phase
6. Fills all columns in the Cloud Resolution tab of the catalog Excel
7. Removes any pre-existing non-user rows from the tab (if instructed)
8. Outputs the updated Excel file

---

## Step 1 — Read Installed Skills

```bash
ls /mnt/skills/user/
```

List all skill folder names. These are the skills to be registered.

---

## Step 2 — Propose Compliant Names

Apply the naming convention:

```
[DEPT]-[FUNCTION]-[TYPE]-[##]
```

- **DEPT**: Use `cres` (Cloud Resolution) as default unless the user specifies otherwise
- **FUNCTION**: Short abbreviation of the skill's purpose (max ~8 chars, lowercase)
  - Examples: `azevtlog`, `vmprf`, `vmutil`, `incres`, `escal`, `shfthnd`, `vmrpt`, `vminv`, `recmd`
- **TYPE**: Always use `wkf` (Workflow) unless the user specifies `agt` (Agent) or `aut` (Automation)
- **##**: Use `01` for all unless duplicates exist

**Department codes available:**
`gcoc, cres, cdel, appo, prob, cinf, cplt, cnet, dba, ecres, ecdel, ecdba, ecprb, fnop, xdep, othr`

Show the user a mapping table like this:

| Current Name | Proposed Name |
|---|---|
| azure-event-logs | cres-azevtlog-wkf-01 |
| ... | ... |

Then ask explicitly:

> "Do these names look correct? Please confirm or suggest changes before I rename anything. I will not touch any skill folders until you approve."

**HARD STOP — do not proceed to Step 3 until the user has replied with explicit approval.**
If the user wants to change any name, update the proposed name and show the table again before asking for re-confirmation.

---

## Step 3 — Rename Skill Folders

Once confirmed, rename each folder:

```bash
cd /mnt/skills/user
mv [old-name] [new-name]
```

---

## Step 4 — Ask About Phases

**Before generating the Excel output**, ask the user to confirm the Phase for each skill.

Present a table like this:

| Skill | What it does (brief) | Phase? |
|---|---|---|
| cres-azevtlog-wkf-01 | Pulls Windows Event Logs from Azure | ? |
| ... | ... | ? |

**Valid phases:**
- `Concept` — idea only, not yet built
- `Defined` — purpose agreed, ready to build
- `In Build` — actively being developed
- `Pilot` — built, running in limited/supervised use
- `Live` — in production with override in place
- `Optimizing` — live and being tuned
- `Retired` — decommissioned

Do **not** proceed to Excel generation until the user has confirmed all phases.

---

## Step 5 — Derive Security Gates

Map Phase → Security Gate automatically using this rule from the GCO catalog:

| Phase | Security Gate |
|---|---|
| Concept | SEC-1 Scope (Pending) |
| Defined | SEC-2 Design (Pending) |
| In Build | SEC-3 Pre-Pilot (Pending) |
| Pilot | SEC-4 Go-Live (Pending) |
| Live | SEC-4 Go-Live (Cleared) |
| Optimizing | SEC-5 Recert (Pending) |
| Retired | SEC-6 Decommission (Pending) |

---

## Step 6 — Fill the Excel Catalog

### Load the catalog

```python
from openpyxl import load_workbook
from copy import copy

wb = load_workbook('Quorum_GCO_AI_Agent_Catalog.xlsx')
ws = wb['Cloud Resolution']
```

### Column mapping (Cloud Resolution tab)

| Col | Field |
|---|---|
| A | Agent / Asset Name (Naming Convention) |
| B | Type (Maturity Stage) |
| C | Phase |
| D | Security Gate (Sign-off) |
| E | Purpose (Use Case) |
| F | Definition (Org-Agreed) |
| G | Owner / Lead |
| H | Shared By (Other Teams) |
| I | Status / Notes |

### Field derivation rules

- **Col A** — New compliant skill name (uppercase), e.g. `CRES-AZEVTLOG-WKF-01`
- **Col B** — Map TYPE code to full word: `wkf` → `Workflow`, `agt` → `Agent`, `aut` → `Automation`
- **Col C** — Phase confirmed by user
- **Col D** — Security Gate derived from Phase (Step 5)
- **Col E** — Purpose: one concise sentence describing what the skill does for the user
- **Col F** — Definition: one to two sentences describing how the skill works technically
- **Col G** — `Cloud Resolution` (default owner)
- **Col H** — Infer from skill scope: VM/infra skills → `GCOC, Cloud Infrastructure`; handover/triage → `GCOC`; escalation → `GCOC, Problem Management`; etc.
- **Col I** — Status/Notes: one short operational note (e.g. read-only, never auto-sends, pairs with X)

### Deriving Purpose and Definition from skill name

Use the FUNCTION part of the skill name to infer purpose and definition:

| Function token | Purpose hint | Definition hint |
|---|---|---|
| `azevtlog` | Pull Windows Event Logs from Azure Arc servers | Queries Azure Monitor Log Analytics; filters Critical/Error/Warning; produces ranked error summary |
| `vmprf` | Analyze Azure VM CPU/RAM/Disk performance | Pulls historical metrics from Azure Monitor; renders colour-coded charts; rightsizing recommendations |
| `vmutil` | Pull real-time Azure VM utilization | Pulls VM resource utilization with hardware specs; identifies servers nearing exhaustion |
| `vminv` | Pull VM/Arc server inventory with utilization trends | Connects to Azure subscriptions; pulls specs and metrics; exports Excel; capacity report |
| `vmrpt` | VM CPU/RAM snapshot posted to ADO incident | Generates colour-coded metrics table; exports Excel; posts as ADO comment |
| `recmd` | Suggest known fixes for incoming incidents | Matches symptoms to known-error library; returns recommended runbook and steps |
| `incres` | Full incident resolution workflow in ADO | Fetches ticket and comments; validates area path; produces Markdown resolution note |
| `escal` | Full escalation ticket workflow in ADO | Fetches parent ticket; builds draft escalation; waits for confirmation; creates ADO ticket |
| `shfthnd` | Generate shift handover package | Pulls ADO tickets; derives next actions; produces Excel + HTML email draft |

For skill names not in the table above, infer from the function token using common sense.

### Copy row styling from existing data rows

```python
from copy import copy

def copy_cell_style(source_cell, target_cell):
    if source_cell.has_style:
        target_cell.font = copy(source_cell.font)
        target_cell.fill = copy(source_cell.fill)
        target_cell.border = copy(source_cell.border)
        target_cell.alignment = copy(source_cell.alignment)
        target_cell.number_format = source_cell.number_format
```

Copy style from row 5 (first data row) when writing new rows.

### Find the next empty row after headers

```python
start_row = 5
for row in ws.iter_rows(min_row=5):
    if all(cell.value is None for cell in row):
        start_row = row[0].row
        break
```

### Optionally clear existing data rows

If the user asks to replace existing entries (not just add), delete rows 5 onward before writing:

```python
ws.delete_rows(5, ws.max_row)
```

---

## Step 7 — Save and Output

```python
wb.save('Quorum_GCO_AI_Agent_Catalog_updated.xlsx')
```

Copy to outputs and present to user:

```bash
cp Quorum_GCO_AI_Agent_Catalog_updated.xlsx /mnt/user-data/outputs/
```

Then call `present_files` with the output path.

---

## Important Rules

- **Never rename skill folders without user confirmation** of the proposed names
- **Never write to the Excel file without phase confirmation** from the user
- **Never auto-send or modify ADO tickets** — this skill is read/write for local files only
- **Always preserve rows 1–4** in the Cloud Resolution tab (title, subtitle, blank, headers)
- **Always uppercase** the skill name in Col A (e.g. `CRES-AZEVTLOG-WKF-01`)
- If the catalog Excel is not uploaded, ask the user to upload `Quorum_GCO_AI_Agent_Catalog.xlsx` before proceeding
- If the user's skills are already named with the correct convention, skip Step 2 and 3

---

## Example Output Summary

After completion, show the user a confirmation table:

| Skill | Phase | Security Gate | Written to Excel |
|---|---|---|---|
| CRES-AZEVTLOG-WKF-01 | Pilot | SEC-4 Go-Live (Pending) | ✅ |
| CRES-INCRES-WKF-01 | Live | SEC-4 Go-Live (Cleared) | ✅ |
| ... | ... | ... | ... |

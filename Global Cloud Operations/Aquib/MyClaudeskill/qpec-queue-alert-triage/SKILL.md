---
name: qpec-queue-alert-triage
description: L2 first-pass triage for QHealth QPEC job-queue alerts on Quorum QCloud environments - QpecQueueStalled, QpecJobRunningTooLong, QpecStaleWorkerRows, QHealthOrphanedRowsGrowing and QHealthAbandonedWorkGrowing. Use this whenever a PagerDuty or Grafana alert or an ADO incident mentions "QPEC - Job running too long", a job in PRC for hours, jobs queued but not starting, a stalled queue, stale or orphaned queue rows, abandoned work, RB0095, RB0096 or RB0097, the qhealth_alert folder, the "QHealth - job queue" dashboard, or a title like "[qcloud]-[RB00xx]-[ENV-Unknown-QPEC-issue]-[app]". It tells L2 which read-only SQL and PowerShell checks to run, how to classify the cause (long job, hung step, dead row, stalled queue, DB problem), when to involve DBAs, the App Owner or Engineering, and produces a paste-ready ADO comment. Use it even if the user only pastes the alert text or an incident number and asks "what do I check".
---

# QPEC queue alert triage (L2 first pass)

Five alerts come from the QHealth monitoring agent, which reads the `QARCH_QUEU_PROCESS` queue table on each SQL server about once a minute. Every one of them is a version of "a queue row stopped moving". Your job is a fast first pass: work out which kind of stuck it is, gather evidence, and end with a verdict, a paste-ready ADO comment, and the right hand-off (DBA, App Owner, Engineering) when the first pass cannot settle it.

This skill is a first-pass guide, not a root-cause analysis. If users are impacted or an outage is confirmed, switch to the `qso-rca` skill and keep the evidence you gathered here.

## Rules (and why)

- **Report times in CST.** Team standard. The QFC database and QPEC server logs use the server's Central local time; PagerDuty, Windows event logs, vCenter and Aria use UTC. Check the offset for the date and convert before writing anything down.
- **Read-only first.** Only `SELECT` on `QARCH_*` tables and read-only PowerShell. Never run UPDATE, DELETE or status changes on queue rows, and never kill or restart a QPEC without the gate in `references/escalation.md`. A stuck row or process is also your best evidence, and it disappears when someone "fixes" it.
- **Evidence before action.** Capture what you saw (query output, process and connection data, log state) before anything is restarted, because a restart erases the process state that explains the hang.
- **Report only what the data shows.** Separate confirmed facts from hypotheses ("consistent with ..."). "Cause not determined" is a valid verdict. The alert text claims things (for example "genuinely executing") that you must verify, not repeat.
- **Never update ADO directly.** Draft the comment for the technician to paste. ADO comments use plain markdown only: no triple-backtick code fences, single-backtick inline code for identifiers and log strings only.
- **No secrets.** Do not paste credentials, connection strings, tokens or config lines. When searching config files, print file paths only. A process dump contains memory: keep it out of ADO.
- **No em dashes** in anything you write; use a hyphen.

## Step 0: Read the alert

Capture these from the alert (PagerDuty, Grafana, or the ADO incident description):

| Item | Where | Use |
|---|---|---|
| `alertname` | labels | Picks the section below. Key on this, not on the runbook ID: the RB number printed in an alert has not always matched the monitoring guide. |
| `database` | labels | The QFC database to query (for example `<ENV>_QFC`). |
| `vm` | labels | The SQL server to connect to. |
| `environment_tier` | labels | Environment name; use it to search ADO for history. |
| `system_manager` | labels | The CTX / System Manager servers that host the QPECs. Log in here for process checks. |
| Time fired | alert | Convert to CST. |
| Count in description | annotation | For example "1 job(s)". |

Route by `alertname`:

| alertname | Plain meaning | Section |
|---|---|---|
| `QpecQueueStalled` | Work is waiting, nothing has started for over an hour, nothing is processing | 1 |
| `QpecJobRunningTooLong` | A job has been in PRC with no end time past the threshold | 2 |
| `QpecStaleWorkerRows` | PRC rows exist but nothing started in the last hour | 3 |
| `QHealthOrphanedRowsGrowing` | New rows that started and were never closed out keep appearing | 4 |
| `QHealthAbandonedWorkGrowing` | Queued work keeps crossing the 7-day never-started line | 5 |

If the alert name is not in this list, say so and use the closest section only for the table and tool names; do not guess at the alert's rule.

## Common first pass (all alerts)

1. Confirm the alert is still firing (Grafana alert view, or ask the technician). A cleared alert still gets a verdict, but the state may have changed since it fired: capture it now.
2. Search ADO read-only for the same environment and alert (work item search on the environment name and "QPEC"). Note earlier occurrences, their dates, what was found and what closed them. Recurrence turns a one-off into a problem-record candidate.
3. Open the "QHealth - job queue" dashboard filtered to the database. The panel names used below come from the monitoring guide.
4. Connect read-only to the `vm` server and the `database` named in the alert. Queries are in `references/sql-queries.md` (labelled Q-A, Q-B and so on).
5. Go to the section for the alert. Finish with a verdict and the comment (see "Finish" below).

Table, column and status-code meanings: `references/tables-and-alerts.md`. Status codes seen in data but not defined in the guides are listed there as unconfirmed; the dashboard's Status reference panel is the authority.

## Section 1: QpecQueueStalled

**Fires when:** work has been queued over 10 minutes, no job has started for between 1 hour and 7 days, and nothing is in PRC, held for 5 minutes. One page per database. It does not fire when the queue is still moving but one job type piles up (that is starvation).

**Check, in order:**

1. Q-B queue overview and Q-D starts per hour: confirm the gap and find the last start time per QPEC server (Q-E).
2. Q-C what is waiting: how old, which process codes, and which statuses. `QUE` rows are waiting for a QPEC; `WPP` rows are waiting for a parent job to finish (a dependency chain, not a stall); held rows (`HLD`, `HS`) are deliberate.
3. QPEC servers (`system_manager` label): System Manager state of each QPEC (Active, STPER, non-active, rogue), QPEC processes alive (PS-2), last write time of QPEC logs, and the self-shutdown signature (PS-8).
4. Was the database reachable? Ask for MT `qtrace` DB connection errors in the window, and SQL server System event log (UTC) for clock steps and service timeouts (PS-10). If the DB was down, QPECs exit by design when they cannot read the queue.
5. Capacity or stall? Q-O peak running jobs. A real capacity problem shows running jobs equal to the QPEC count and waits that clear; zero starts is not capacity.

**Verdicts:**

| Finding | Verdict | Next step |
|---|---|---|
| Alert cleared, jobs starting again | Transient stall | Document the gap window (last start, first start after) and the cause if visible |
| QPECs Active, rows in `QUE`, zero starts | QPECs alive but not polling | App Owner approval, evidence per `references/escalation.md`, then STOP / KILL / START; verify with Q-D and Q-E that a queued job starts |
| QPECs stopped, STPER or non-active | QPEC down | Restart via System Manager; restart one at a time (two QPECs restarting together can be falsely marked STPER, Bug 1780230) |
| DB unreachable or slow in the window | Database or host problem | DBA, plus infra for VM/host evidence (`references/escalation.md`) |
| Waiting rows are `WPP` or held | Not a stall | Find the parent job (Section 2 or 3) or ask who held it |

## Section 2: QpecJobRunningTooLong

**Fires when:** the longest PRC job of a job type passes the threshold with no end time, held 10 minutes. One page per database with a count. The monitoring guide says 2 hours; on at least one environment the threshold was raised to 4 hours, so read the number in the alert text. The alert text says the jobs are "genuinely executing". Treat that as a claim to test: the metric excludes rows that errored without being closed out, but a hung job and a dead row can both still look like this.

**Check, in order:**

1. Q-A: list every PRC row with no end time (all of them, not only the newest; a past review missed the row by reading only the top result). Rows months old are dead rows, not the alert source: note them separately. The alert is normally the recent one (`running_min` close to the alert age).
2. Q-G steps of the job: which step is in `PRC` and when it started. Q-H how long that step normally takes. A step in PRC for hours against a baseline of seconds is the signal.
3. Q-I baseline for the process code: normal, 95th percentile and longest completed runs. A run far beyond the longest ever completed is abnormal; a process that routinely runs for hours is just long.
4. Q-K children, if the job has any: compare `CHILD_PROCESS_COUNT_COMPLETE` between two runs a few minutes apart. Rising means progress.
5. Who owns the row? Q-F and the System Manager "QPEC Instance Status" screen (System Process ID, status, current process and step). The two sources can disagree (the table can show no active process while System Manager shows ACTIVE), so record both and do not rely on one.
6. On the QPEC server (PS-1 to PS-5): get the PID from the per-run log file name `RealTimeMsgLog_<PROCESS_ID>_<PID>_<PROCESS_QUEUE_ID>.log`; check that process exists and was created before the job started; sample CPU twice 60 seconds apart; list its connections with creation times; test the remote endpoints; check whether the per-run log has any content.
7. Q-J: is the same step stuck in other rows? A pattern across rows, users or QPEC servers points to a recurring defect or dependency rather than bad luck. Search ADO for the step name (read-only).
8. If the verdict is "blocked" or you need to see what the process is waiting on, hand the DBA the queries in Q-P (L2 lacks VIEW SERVER STATE).

**Verdicts:**

| Finding | Verdict | Next step |
|---|---|---|
| Row has an end date now, alert cleared | Finished | Record duration against baseline; close, note if it was much longer than usual |
| Baseline shows runs this long, or children or steps are advancing, or CPU is rising | Genuinely long | Tell the App Owner the job type, start and expected behaviour; suggest a threshold review if routine |
| Process alive, CPU flat, connections idle, step far beyond baseline, per-run log empty | Hung step | App Owner (is the job safe to kill and re-run?), DBA (what the DB sessions wait on), Engineering (dump); evidence first, then approved STOP / KILL |
| No such process, or process created after the job started, or no QPEC ever claimed it | Dead row | App Owner / DBA approve row clean-up (data change); find why the worker died (restart, memory exit, kill, STPER, DB outage) |
| DBA shows a blocking chain | Blocked | DBA identifies the head blocker; App Owner decides |

A worked example (anonymized) is in `references/worked-example-hung-step.md`.

## Section 3: QpecStaleWorkerRows

**Fires when:** rows are in PRC and no job has started in the last hour, held 30 minutes. The condition is about rows and starts, not about whether a process is alive, so two situations trigger it: a worker that died without closing its row, and a genuine long job running while nothing else is scheduled. It can also hide a stalled queue.

**Check, in order:**

1. Q-A PRC rows and their ages, Q-E last start time, and Q-B whether anything is waiting in `QUE`. Waiting rows plus no starts means the queue is also stalled: do Section 1 as well.
2. For each PRC row, apply Section 2 steps 5 and 6: does a QPEC claim it, does the process exist and predate the job, is it using CPU.
3. Is the hour quiet by design? Q-D for the same hour on previous days. If nothing normally starts at that hour, a genuine long job is a likely trigger.

**Verdicts:**

| Finding | Verdict | Next step |
|---|---|---|
| Process alive and working on the PRC row, quiet hour | False positive from a long job | Treat as Section 2; mention the quiet-hour trigger to the App Owner |
| No process behind the row | Dead worker rows | Find why the worker died; approved clean-up (App Owner / DBA) |
| Old dead rows (weeks or months) keep the condition true whenever the queue is quiet | Repeat pages from stale rows (inference from the alert definition, not yet proven) | Propose approved clean-up so the alert reflects live problems |
| Rows waiting plus no starts | Stalled queue | Section 1 |

## Section 4: QHealthOrphanedRowsGrowing

**Fires when:** the rate of newly orphaned rows rises. An orphaned row is one whose status and timestamps contradict each other: it started but was never closed out, usually because a worker died mid-job. The level of orphaned rows is history; the rate is the live signal.

**Check, in order:**

1. Dashboard: "Orphaned rows", "Newly orphaned per day", "In flight vs orphaned", "Unfinished by job type and status".
2. Q-L: group candidate rows by status, process code, QPEC server and start day. Pick the dominant process code, server and time window. Use the dashboard Status reference to decide which statuses are terminal; a terminal status with no end date is an orphan.
3. Correlate the start window with QPEC restarts and exits (memory-limit exit around 750 MB with automatic restart about 15 seconds later, STPER, STOP/KILL history in System Manager), reboots or patching, and DB outages.
4. Q-N message logs for two or three sample queue IDs (run this early; logs are purged).

**Verdicts:**

| Finding | Verdict | Next step |
|---|---|---|
| One cluster tied to a restart, patch window or DB outage | One-off | Document the event; suggest approved clean-up; no further action |
| Steady growth for one process code | Application fault in that process | App Owner, then Engineering with sample queue IDs, steps and times |
| Growth across process codes after each QPEC restart | QPEC restart or shutdown handling | Engineering with the restart evidence |
| Growth lines up with DB errors | Database side | DBA |

## Section 5: QHealthAbandonedWorkGrowing

**Fires when:** the rate of queued jobs crossing the 7-day never-started line rises. The standing pile is mostly history; the rate is the signal.

**Check, in order:**

1. Dashboard: "Abandoned by status and job type", "Newly abandoned per day".
2. Q-M: abandoned rows by process code, status and queued day; "newly abandoned" is queued 7 to 8 days ago.
3. Why were they never started? Candidates to check, not proven causes: `ASSIGNED_MACHINE_ID` pointing at a machine that no longer exists, QPECs in assigned-jobs-only mode (Q-F), a parent that never finished (`WPP`, `WTP`; look for it with Q-A and Q-L), rows held on purpose, or a process no QPEC can run.
4. Is it new work crossing the line now (rate above zero) or a steady old pile (rate zero)?

**Verdicts:**

| Finding | Verdict | Next step |
|---|---|---|
| Steady old pile, rate zero | History | Note it; propose approved clean-up |
| New rows for one process code | That job is scheduled but never runs | App Owner: is it still needed, is its schedule or assignment wrong |
| Assigned machine does not exist | Bad assignment | App Owner / Cloud Ops to correct |
| Blocked by a parent that never finished | Dependency stuck | Find the parent (Section 2 or 3) |

DBAs are not normally needed here unless the table size or the queries themselves are a problem.

## Finish: verdict and ADO comment

1. State the verdict (one of the table rows above, or "cause not determined"), the evidence in CST, what was checked, what is not known, and the next steps with the owner for each.
2. Draft the ADO comment from `references/comment-templates.md`: plain markdown, no code fences, queries as short inline code or by name. Do not post it; hand it to the technician.
3. L2 options from the monitoring guide: engage support, disregard the alert (only if it is no longer firing and there is no ongoing impact), restart the service (only with the gate in `references/escalation.md`), or escalate to the App Owner. Document the findings and the action before closing or escalating.
4. If the same alert has fired before on this environment, say so and recommend a problem record rather than another one-off close.

## Limits of this skill

The SQL and commands were proven on real cases only where marked in `references/sql-queries.md` and `references/powershell-checks.md`. Status codes beyond `QUE`, `PIK`, `PRC` and `WPP` are not defined in the source guides. Section 4 and 5 queries are untested drafts built from the dashboard definitions. Run each query once on the real environment and sanity-check the output before relying on it, then update the file.

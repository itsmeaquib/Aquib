# Escalation, hand-offs and the restart gate

Contents: who to involve and when, the gate before any STOP / KILL / row change, the sequence, what to hand to each team, and when to switch to a full RCA.

## Who to involve and when

| Team | Involve when | What they can do that L2 cannot |
|---|---|---|
| App Owner (for the application behind the job, for example Upstream, TIPS, QPTM) | Any verdict that needs a decision about a job or data: is the job safe to kill and re-run, is a long job expected, is the job still needed, clean-up of rows | Know what the job and its steps do, what they connect to, and whether a stopped run left partial changes |
| DBA | The job may be blocked or waiting inside the database; you need session, wait and transaction data (VIEW SERVER STATE); the DB was slow or unreachable in the window; an Oracle endpoint is involved | DMVs (`sys.dm_exec_sessions`, `sys.dm_exec_requests`), Oracle `v$session`, blocking chains, approved row clean-up |
| Infra (VM / host) | The DB server stalled but SQL and disk errors are absent: clock steps, service timeouts, snapshot or vMotion events, host memory | vCenter and Aria evidence for the VM, its hosts and datastores |
| Engineering (product) | A hang, orphan growth or restart-handling problem looks like a code defect and will recur; a process dump is available; the same step has hung several times | Dump analysis (thread stacks, socket waits), timeout and retry behaviour in the code |
| Cloud Ops / SRE | The alert needs tuning, a problem record, or a monitoring change | Threshold changes, runbook updates, problem tickets |

Engineering routing used by the RCA skill: Upstream Suite (QRA, QDO, QCA, QCFS) to Davison Oliver; Land Suite (QLS, QLA, QGIS) to Asher Maddox; others per the current CloudOps escalation matrix. The engineering SLO is 3 days. Confirm names against the current matrix before using them.

Recurrence rule: if the same alert and the same step or process has fired before on the environment (check ADO), recommend a problem record and say how many times it has happened, not another one-off close.

## Gate before any STOP, KILL, restart or row change

Do not proceed until every item is true. The reasons are in brackets.

1. **The database is reachable** (restarting QPECs against an unreachable database does not help, and System Manager may already have restarted them into the same outage).
2. **Evidence is captured and written down**: Q-A, Q-B, Q-F output; step rows (Q-G, Q-J); PS-2, PS-3, PS-4 output with times; the per-run log state; the System Manager instance screen. A process dump (PS-9) if Engineering may want one and the App Owner agrees. (The process state that explains a hang is lost on restart.)
3. **The DBA session data is captured if a DBA is available the same day** (sessions vanish with the process). If no DBA is available, say so in the comment and continue; do not hold a stuck job indefinitely for it.
4. **The App Owner approves**, knowing the job may be partly done: a stopped job can leave partial changes, and a re-run may repeat them. Customer approval too if the customer asked to approve restarts. Record who approved and when.
5. **Only one QPEC is restarted at a time** (two QPECs restarting at nearly the same moment can get one falsely marked STPER by System Manager, Bug 1780230).

## Sequence

1. In System Manager, STOP the QPEC instance that holds the job (find it by the PID and instance number from the checks).
2. If it does not stop, KILL it (it has taken two KILLs before).
3. START it.
4. Verify a queued job actually starts (Q-D, Q-E) before telling anyone it is fixed.
5. Record who did what and when. Note that the stuck queue row will usually stay in `PRC` after the process is killed (older rows left that way); clearing it is a separate data change by the App Owner or DBA with approval. Do not edit the row yourself.

## What to hand over

**To a DBA:** the QFC database name and SQL server, the QPEC server name, the job's `PROCESS_QUEUE_ID` and start time (CST and server local), the Q-P queries, and that the sessions must be captured before the QPEC is killed.

**To Engineering:** environment and deployed version, alert and ticket, the process code and step, the queue IDs, the timeline with times in CST, steps and baselines from Q-G/Q-H/Q-I/Q-J, PS-2 to PS-6 output, whether the per-run log was empty, the dump location and time (not the dump itself in ADO), the pattern across rows (servers, users, dates), related ADO items, and the specific questions (what is the step waiting on, is there a call timeout, why is the row left in `PRC`).

**To Infra:** the SQL server and window, clock-step findings from PS-10, and that SQL and disk errors were absent if so.

## When to switch to a full RCA

If users were impacted, the application was down, or the ticket becomes a Problem needing a root-cause write-up, switch to the `qso-rca` skill and bring the evidence from this pass. For jobs-not-processing outages the investigation guide `QPEC_Jobs_Not_Processing_Investigation_Guide.md` (if available in the team's runbooks folder) has the longer set of queries and a reference case library.

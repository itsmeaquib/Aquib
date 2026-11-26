# ADO comment templates

Use these to draft the comment for the technician to paste into the ADO ticket. Do not post it.

Format rules (ADO renders triple-backtick fences as literal text):
- Plain markdown only. No code fences.
- Single-backtick inline code only for identifiers, table names, process codes, server names and short log strings. A query may be given as one short inline line or by name (for example "Q-A"); put long SQL in an attached file instead.
- All times CST, with the zone stated once at the top.
- Facts and hypotheses kept apart: confirmed findings in "What was checked", guesses in "Not known" or phrased "consistent with".
- No credentials, no config lines, no dump contents, no customer data beyond what the ticket already shows. Refer to a dump by path and time only.
- No em dashes.

Replace every `<...>` placeholder. Delete lines that do not apply. Copy only what is between the lines.

## Skeleton (all alerts)

---
L2 first-pass review. All times CST. Alert `<alertname>` on `<database>` (`<vm>`), environment `<environment_tier>`, fired <time>.

Summary: <verdict in one or two sentences, in plain language>. Root cause: <not determined / what was found>.

What was checked:
1. <Query or check name>: <finding with numbers and times>.
2. <...>

Verdict: <one of the verdicts for this alert, with the evidence that decides it>.

Not known: <what the data does not show; for example what the step is waiting on>.

History: <earlier occurrences on this environment with dates and ticket numbers, or "none found">.

Next steps:
1. <owner>: <action>.
2. <owner>: <action>.

<Do not restart or kill the QPEC until ... / Evidence captured: ...>
---

## QpecJobRunningTooLong verdict lines

Finished: Job `<PROCESS_QUEUE_ID>` (`<PROCESS_ID>`) finished at <time> after <duration>, against a normal range of <p50> to <longest> for this process. The alert has cleared. <No action / note for App Owner>.

Genuinely long: Job `<PROCESS_QUEUE_ID>` (`<PROCESS_ID>`) has run <duration>. This process has completed runs of up to <longest>, and <children advanced from X to Y in Z minutes / CPU is rising>. Consistent with a long but working job. App Owner to confirm the expected duration.

Hung step: Job `<PROCESS_QUEUE_ID>` (`<PROCESS_ID>`, submitted <time> by `<user>`) has been in step `<STEP_ID>` since <time> (<duration>). That step normally takes <range>. The QPEC process (PID <pid>, created <time>, before the job) is alive and idle: CPU moved <x> s in 60 s, the per-run log is empty, and it holds a connection to `<host:port>` opened at <time>. Consistent with a hung step; the cause is not determined. <Same step stuck in N other rows: dates/servers.> A process dump was taken at <time> (<path>).

Dead row: Job `<PROCESS_QUEUE_ID>` (`<PROCESS_ID>`) shows `PRC` since <time>, but no QPEC process <exists with PID <pid> / was created before the job>. The row appears to be left over from a worker that died. <Cause if found: restart at <time> / not determined>.

Blocked: The DBA found session <id> blocked by <id>; head blocker <details>. <DBA / App Owner action>.

Old PRC rows: <N> older PRC rows (<ids and dates>) are months old and look like dead rows; they are not the source of this alert.

## QpecQueueStalled verdict lines

Transient: No jobs started between <time> and <time> (<duration>) while <N> jobs were queued. Jobs resumed at <time>. <Cause found / not determined>.

QPECs not polling: <N> jobs in `QUE`, oldest queued <time>, no starts since <time> on `<server>`, while the QPECs show Active and run. Consistent with QPECs alive but not polling. App Owner approval requested for restart (one QPEC at a time).

QPECs down: QPEC(s) `<instance>` on `<server>` were in <STPER / non-active> since <time>. <Restart action and verification>.

Database or host: The database was <unreachable / slow> from <time> to <time> (<evidence>). QPECs <exited by design at <time> (log signature) / ...>. DBA and Infra to review.

Dependency chain, not a stall: Waiting rows are in `WPP` behind parent job `<id>` (`<process>`), which has been in <status> since <time>. See the parent.

## QpecStaleWorkerRows verdict lines

False positive from a long job: The only PRC row is job `<id>` (`<process>`), alive and working (<evidence>), and no new jobs are normally scheduled at this hour (<Q-D comparison>). Treated as a long-running job.

Dead worker rows: <N> PRC rows have no process behind them. Latest started <time>. <Cause or not determined>. Clean-up proposed for App Owner or DBA approval.

## QHealthOrphanedRowsGrowing verdict lines

One-off cluster: <N> rows started between <time> and <time> on `<server>` were never closed, coinciding with <restart / patch / DB outage>. No new rows since <time>.

Ongoing: <N> new orphaned rows per day for `<process>` since <date>, <on server / across servers>. No restart or outage lines up. Sample queue IDs: <ids>. Engineering to review.

## QHealthAbandonedWorkGrowing verdict lines

History: <N> rows older than 7 days, none newly crossing (0 queued 7 to 8 days ago). Standing pile only; clean-up proposed.

Growing: <N> rows of `<process>` queued 7 to 8 days ago never started; <assigned machine missing / parent never finished / not determined>. App Owner to confirm whether the job is still needed.

## When disregarding the alert

Only if the alert has stopped firing and there is no ongoing impact. State what was checked, that the state is now normal, and the evidence time:

---
Alert `<alertname>` has stopped firing at <time>. Checks: <list>. Current state: <normal evidence>. No user impact reported. Closing as <transient / long job that finished>. Occurrences on this environment: <count and dates>; <problem record recommended / not needed>.
---

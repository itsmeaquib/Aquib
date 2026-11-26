# Tables, alert definitions, status codes and dashboard map

Source: the "QPEC Job Queue Monitoring" guide (dashboard and alert definitions) and the QPEC "jobs not processing" investigation guide, plus what was observed on real cases. Where something is not defined in those sources it is marked unconfirmed.

Contents: how the monitoring works, the five alerts, dashboard panels, tables and columns, status codes, time conventions, precedent cases.

## How the monitoring works

QPEC runs background jobs (imports, calculations, reports). Every job is a row in `QARCH_QUEU_PROCESS` inside each application's QFC database. A QPEC picks a job up, runs it, and marks it finished. A monitoring agent on each SQL server reads the queue tables about once a minute and publishes metrics; the "QHealth - job queue" Grafana dashboard shows them and the alerts in the `qhealth_alert` folder page the team. If the agent stops, numbers disappear rather than going to zero.

Healthy jobs move through status, queue time, start time and end time in order. Every alert is a row (or set of rows) that stopped moving.

All five alerts are Sev2, route to PagerDuty and repeat every 10 minutes while the condition holds. Each fires per database, and the resource on the page is the System Manager server(s) for that database's environment, which is where you log in to investigate.

## The five alerts

| alertname | Condition | Held for | Does not catch |
|---|---|---|---|
| `QpecQueueStalled` | Work queued over 10 minutes; no job started for between 1 hour and 7 days; nothing in PRC | 5 min | A queue that is still moving while one job type piles up (starvation). The 7-day upper limit hands very old never-run work to the abandoned alert. |
| `QpecJobRunningTooLong` | Longest PRC job of a job type past the threshold with no end time (the guide says 2 hours; raised to 4 hours on at least one environment, read the alert text) | 10 min | Rows that errored without being closed out (counted as orphaned instead). One page per database with a count. Metric: `qhealth_job_type_longest_running_seconds{status_cd="PRC"}`. |
| `QpecStaleWorkerRows` | PRC rows exist and zero jobs started in the last hour | 30 min | Whether a process is alive; a long genuine job in a quiet hour also satisfies it. Phantom PRC rows can also stop the stalled alert from firing. |
| `QHealthOrphanedRowsGrowing` | Rate of newly orphaned rows (started, never closed out) per day | per rule | The standing level (history). |
| `QHealthAbandonedWorkGrowing` | Rate of queued work crossing the 7-day never-started line | per rule | The standing pile (history). |

The runbook ID in an alert has not always matched the guide (the guide lists RB0095 for the stalled queue, RB0096 for running too long and RB0097 for stale worker rows, while a running-too-long ticket cited RB0095). Use `alertname`.

## Dashboard panels (QHealth - job queue)

Filters: SQL server, database, environment tier, product. "Host environment" is the VM's label set at install; "Environment tier" is derived from the database name.

| Area | Panels | Use for |
|---|---|---|
| Fleet overview | Databases collected, Stalled now, Waiting (live), Abandoned, Held, Processing now, Orphaned, Longest wait | Quick state. "Processing now" counts dead PRC rows too, so a high number with no recent starts means dead rows, not activity. |
| Is the queue moving | Time since a job last started; Throughput (started vs finished per hour) | Stall signal. "No start in window" means nothing started in the 2-day lookback (or the DB could not be read). |
| Work waiting | Queued by age; Oldest queued job; Backlog by status (live); Held vs waiting; Queued by job type (live) | What is waiting and how old. "Live" means queued in the last 7 days. |
| Work in progress | Active jobs; Running longer than 1, 2, 6 hours; Longest-running job; In flight vs orphaned; Unfinished by job type and status | Long and stuck jobs. Processing high with started-in-last-hour at zero means dead worker rows. |
| Abandoned work | Abandoned total; Newly abandoned per day; Abandoned by status and job type; Orphaned rows; Newly orphaned per day | The two growth alerts. |
| Collection health | Discovered / Agents reporting; Not collected; Missing a grant; Discovery gap | If totals look low, check that the agent is reporting before trusting them. |
| Status reference | Every status code and its group (not started, held, in flight, terminal) | The authority for status meanings. |

## Tables and columns (QFC database)

| Table | Holds | Columns used |
|---|---|---|
| `QARCH_QUEU_PROCESS` | One row per queued or executed batch process | `PROCESS_QUEUE_ID`, `PROCESS_ID` (job code), `STATUS_CD`, `LOCAL_MACHINE_ID` (QPEC server that ran it), `ASSIGNED_MACHINE_ID`, `EXECUTE_ATTEMPTS`, `QUEUE_DT`, `START_DT`, `END_DT`, `STATUS_CHANGE_HISTORY`, `PROCESS_STATUS_DESCR`, `UPDT_DT`, `USER_ID`, `MASTER_PROCESS_QUEUE_ID`, `PARENT_PROCESS_QUEUE_ID`, `CHILD_PROCESS_COUNT`, `CHILD_PROCESS_COUNT_COMPLETE` |
| `QARCH_QUEU_PROCESS_STEP` | The steps of a run | `PROCESS_STEP_QUEUE_ID`, `PROCESS_QUEUE_ID`, `PROCESS_STEP_ID`, `SEQ_NO`, `STATUS_CD`, `START_DT`, `END_DT` |
| `QARCH_QPEC_STATUS` | One row per QPEC instance and what it is doing | `QPEC_INSTANCE_ID`, `QPEC_MACHINE_NM`, `SYSTEM_PROCESS_ID` (Windows PID), `PROCESS_ACTIVE_IND`, `PROCESS_ID`, `PROCESS_QUEUE_ID`, `QPEC_MODE`, `ASSIGNED_JOBS_ONLY_IND`, `USER_ID`, `UPDT_DT` |
| `QARCH_QPEC_MSG_LOG` | QPEC messages written to the DB | `LOG_ID`, `LOCAL_MACHINE_ID`, `PROCESS_QUEUE_ID`, `LOG_MSG_TYPE_CD`, `LOG_DATE`, `LOG_MSG` |
| `QARCH_PROCESS_MSG_LOG`, `QARCH_STG_PROCESS_MSG_LOG` | Per-run messages and their staging | Often empty for a hung or long run; purged over time |
| `QARCH_QPEC_PROCESS_STATS` | QPEC statistics per interval | Check it is populated before relying on it |
| `QARCH_QFCBATCH_SQL_TRACE` | Batch execution history and SQL (TIPS) | Not examined in these cases |

## Status codes

Confirmed by the guides: `QUE` queued, `PIK` picked up by a QPEC, `PRC` processing (the only code that means genuinely executing), `WPP` waiting on a parent process. From the monitoring guide's groups: not started = `BQU`, `QUE`, `SCH`, `WTP`, `PIK`; held = `HLD`, `HS`; in flight = `PRC` plus the waiting-on-child, lock or dependency codes. `WTL` appeared in a ticket as the state of jobs waiting for a lock (unconfirmed).

Observed in data, meaning not defined in the guides (unconfirmed): `CS` (the code on the large majority of finished runs, treated as completed), `CW` (appeared on finished runs, treated as completed with warnings), `CSE`, `CE`, `SPE`, `SE`, `SX`, `SXI`, `SXL`, `SXE`, `UX`. One run that was stuck about 16 hours ended with `SE`; what ended it was not recorded. Use the dashboard Status reference panel and do not state a meaning you have not confirmed. A status seen at report time can differ from a later query, so capture state early.

## Time conventions

Server logs and the QFC database use the server's local time (Central; CDT until early November, CST after). Windows event logs, vCenter, Aria and PagerDuty use UTC. State the zone, check the offset for the date, and report CST in notes. The team standard is CST only.

## Related facts

- QPEC is configured to self-exit when its own memory passes about 750 MB and restart about 15 seconds later. Do not read that exit as a user-facing outage.
- Bug 1780230: when two QPEC processes restart at nearly the same time, System Manager can falsely mark the second one STPER (Stopped on Error). It is a System Manager defect.
- QPEC servers are not in the critical path for web or Citrix sessions. Do not link a QPEC alert to a user-facing outage without log evidence.
- Precedent reference cases (investigation guide): a database VM stall where all QPECs exited by design and then did not poll (jobs queued, zero starts for hours); a slow-database case where every database-bound step was slower while pickup waits stayed at 0 to 2 seconds. Both show the "queue" alerts firing for different underlying causes.

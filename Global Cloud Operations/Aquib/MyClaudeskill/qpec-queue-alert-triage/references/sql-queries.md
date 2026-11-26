# SQL queries for QPEC queue alert triage

Read-only. Run in the QFC database named in the alert's `database` label, on the SQL server named in the `vm` label (SQL Server syntax). Times are the SQL server's local time (Central); convert to CST for notes. The QFC database holds the queue tables; each application has its own, so use the one in the alert.

Proof status is marked per query: **proven** = run on a real case and returned sensible data; **adapted** = from the investigation guide, columns confirmed there; **draft** = built from the dashboard definitions, run it once and check the output before relying on it.

Contents: parameters, Q-A open PRC rows, Q-B queue overview, Q-C waiting backlog, Q-D starts per hour, Q-E last start per server, Q-F QPEC instances, Q-G steps of one run, Q-H step baseline, Q-I process baseline, Q-J same step stuck elsewhere, Q-K children, Q-L orphan candidates, Q-M abandoned work, Q-N messages, Q-O peak concurrency, Q-P queries for a DBA.

## Parameters

```sql
DECLARE @Start datetime = '2026-01-01 00:00';   -- window start (server local time)
DECLARE @End   datetime = '2026-01-01 23:59';   -- window end
DECLARE @Pqid  int      = 0;                    -- PROCESS_QUEUE_ID of the run under investigation
```

## Q-A Open PRC rows (proven)

All rows in PRC with no end time. Read every row; old rows are dead rows, the recent one is usually the alert.

```sql
SELECT PROCESS_QUEUE_ID, PROCESS_ID, STATUS_CD, USER_ID, LOCAL_MACHINE_ID, ASSIGNED_MACHINE_ID,
       QUEUE_DT, START_DT, END_DT,
       DATEDIFF(MINUTE, START_DT, GETDATE()) AS running_min,
       MASTER_PROCESS_QUEUE_ID, PARENT_PROCESS_QUEUE_ID,
       CHILD_PROCESS_COUNT, CHILD_PROCESS_COUNT_COMPLETE,
       STATUS_CHANGE_HISTORY, PROCESS_STATUS_DESCR, UPDT_DT
FROM QARCH_QUEU_PROCESS
WHERE STATUS_CD = 'PRC' AND END_DT IS NULL
ORDER BY START_DT;
```

Read: `running_min` against the alert age. `STATUS_CHANGE_HISTORY` such as `QUE*;PIK*;PRC*` shows the transitions; `UPDT_DT` equal to `START_DT` means the row has not been touched since it started. `ASSIGNED_MACHINE_ID` may be NULL; use `LOCAL_MACHINE_ID` for the QPEC server.

## Q-B Queue overview (proven)

```sql
SELECT STATUS_CD, COUNT(*) AS jobs, MIN(QUEUE_DT) AS oldest_queued, MAX(UPDT_DT) AS last_update
FROM QARCH_QUEU_PROCESS
GROUP BY STATUS_CD
ORDER BY jobs DESC;
```

Read: `last_update` on completed statuses shows the queue is moving. Old `QUE` rows are waiting or abandoned. Counts of old history are large and normal.

## Q-C Waiting backlog by process code and age (draft)

```sql
SELECT STATUS_CD, PROCESS_ID, COUNT(*) AS jobs,
       MIN(QUEUE_DT) AS oldest, MAX(QUEUE_DT) AS newest,
       SUM(CASE WHEN QUEUE_DT < DATEADD(DAY, -7, GETDATE()) THEN 1 ELSE 0 END) AS older_than_7d
FROM QARCH_QUEU_PROCESS
WHERE STATUS_CD IN ('BQU','QUE','SCH','WTP','PIK')
GROUP BY STATUS_CD, PROCESS_ID
ORDER BY jobs DESC;
```

The five codes are the "not started" statuses in the monitoring guide. `WPP` (waiting on parent) is separate; include it to see dependency chains.

## Q-D Starts per hour (proven)

```sql
SELECT CAST(START_DT AS date) AS day, DATEPART(HOUR, START_DT) AS hr, COUNT(*) AS starts
FROM QARCH_QUEU_PROCESS
WHERE START_DT >= @Start AND START_DT < @End
GROUP BY CAST(START_DT AS date), DATEPART(HOUR, START_DT)
ORDER BY day, hr;
```

Read: hours missing from the result had no starts. Compare with the same hours on previous days to see whether quiet is normal.

## Q-E Last start per QPEC server (proven)

```sql
SELECT LOCAL_MACHINE_ID, COUNT(*) AS started, MAX(START_DT) AS last_start
FROM QARCH_QUEU_PROCESS
WHERE START_DT >= @Start
GROUP BY LOCAL_MACHINE_ID;
```

Read: every healthy server shows a recent `last_start`. A server whose `last_start` stopped while jobs wait is not polling.

## Q-F QPEC instances (proven)

```sql
SELECT QPEC_INSTANCE_ID, QPEC_MACHINE_NM, SYSTEM_PROCESS_ID, PROCESS_ACTIVE_IND,
       PROCESS_ID, PROCESS_QUEUE_ID, QPEC_MODE, ASSIGNED_JOBS_ONLY_IND, USER_ID, UPDT_DT
FROM QARCH_QPEC_STATUS
ORDER BY QPEC_MACHINE_NM, QPEC_INSTANCE_ID;
```

Read: `SYSTEM_PROCESS_ID` is the Windows PID. `ASSIGNED_JOBS_ONLY_IND=1` instances do not drain the general queue. Ignore rows with a very old `UPDT_DT` (legacy servers from years ago). Caution: a QPEC can be ACTIVE in System Manager while its row here shows `PROCESS_ACTIVE_IND=0` and no process; an instance whose `UPDT_DT` has not moved while all others did may be the one holding a long job. Record both sources, do not rely on this table alone.

## Q-G Steps of one run (proven)

```sql
SELECT PROCESS_STEP_QUEUE_ID, PROCESS_STEP_ID, SEQ_NO, STATUS_CD, START_DT, END_DT
FROM QARCH_QUEU_PROCESS_STEP
WHERE PROCESS_QUEUE_ID = @Pqid
ORDER BY SEQ_NO;
```

Read: the step in `PRC` with no end is where the job is. Earlier steps finishing in seconds and the last one never ending is the hung-step pattern.

## Q-H Normal duration of a step (proven)

```sql
SELECT STATUS_CD, COUNT(*) AS n,
       MIN(DATEDIFF(SECOND, START_DT, END_DT)) AS min_sec,
       AVG(DATEDIFF(SECOND, START_DT, END_DT)) AS avg_sec,
       MAX(DATEDIFF(SECOND, START_DT, END_DT)) AS max_sec
FROM QARCH_QUEU_PROCESS_STEP
WHERE PROCESS_STEP_ID = 'REPLACE_STEP_ID'
GROUP BY STATUS_CD
ORDER BY n DESC;
```

Read: finished runs give the normal range; rows with no duration are steps that never ended (compare their count with Q-J).

## Q-I Baseline for a process code (proven)

Outcomes and durations by status:

```sql
SELECT STATUS_CD, COUNT(*) AS runs,
       MIN(DATEDIFF(SECOND, START_DT, END_DT)) AS min_sec,
       AVG(DATEDIFF(SECOND, START_DT, END_DT)) AS avg_sec,
       MAX(DATEDIFF(SECOND, START_DT, END_DT)) AS max_sec
FROM QARCH_QUEU_PROCESS
WHERE PROCESS_ID = 'REPLACE_PROCESS_ID' AND START_DT IS NOT NULL
GROUP BY STATUS_CD
ORDER BY runs DESC;
```

Percentiles for completed runs (adjust the status list to the codes that mean "completed" on this environment):

```sql
SELECT DISTINCT
  PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY DATEDIFF(SECOND, START_DT, END_DT)) OVER () AS p50_sec,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY DATEDIFF(SECOND, START_DT, END_DT)) OVER () AS p95_sec,
  COUNT(*) OVER () AS runs
FROM QARCH_QUEU_PROCESS
WHERE PROCESS_ID = 'REPLACE_PROCESS_ID' AND STATUS_CD IN ('CS','CW') AND END_DT IS NOT NULL;
```

Longest finished runs with user and server:

```sql
SELECT TOP 20 PROCESS_QUEUE_ID, USER_ID, STATUS_CD, LOCAL_MACHINE_ID, START_DT, END_DT,
       DATEDIFF(MINUTE, START_DT, END_DT) AS run_min
FROM QARCH_QUEU_PROCESS
WHERE PROCESS_ID = 'REPLACE_PROCESS_ID' AND END_DT IS NOT NULL
ORDER BY run_min DESC;
```

Last 30 runs including any still open:

```sql
SELECT TOP 30 PROCESS_QUEUE_ID, USER_ID, STATUS_CD, LOCAL_MACHINE_ID, QUEUE_DT, START_DT, END_DT,
       DATEDIFF(MINUTE, START_DT, ISNULL(END_DT, GETDATE())) AS run_min
FROM QARCH_QUEU_PROCESS
WHERE PROCESS_ID = 'REPLACE_PROCESS_ID'
ORDER BY START_DT DESC;
```

Read: compare the open run with the longest completed run and the 95th percentile. Also see whether other runs of the same process by the same user kept finishing normally while this one hung (the process works in general, one run is stuck), and whether all stuck runs landed on one QPEC server.

## Q-J Same step stuck in other rows (proven)

```sql
SELECT s.PROCESS_QUEUE_ID, p.PROCESS_ID, p.USER_ID, p.LOCAL_MACHINE_ID,
       p.STATUS_CD AS job_status, s.STATUS_CD AS step_status, s.START_DT
FROM QARCH_QUEU_PROCESS_STEP s
LEFT JOIN QARCH_QUEU_PROCESS p ON p.PROCESS_QUEUE_ID = s.PROCESS_QUEUE_ID
WHERE s.PROCESS_STEP_ID = 'REPLACE_STEP_ID' AND s.STATUS_CD = 'PRC'
ORDER BY s.START_DT;
```

Read: a job whose own status is a terminal code (not `PRC`) but whose step is still `PRC` is a run that ended without closing its step. Count the rows and note dates, users, servers and process codes: that is the recurrence pattern for the ticket.

## Q-K Children of a master run (proven in an earlier case)

```sql
SELECT PROCESS_QUEUE_ID, PROCESS_ID, STATUS_CD, QUEUE_DT, START_DT, END_DT,
       DATEDIFF(SECOND, QUEUE_DT, START_DT) AS wait_sec,
       DATEDIFF(SECOND, START_DT, ISNULL(END_DT, GETDATE())) AS run_sec,
       LOCAL_MACHINE_ID
FROM QARCH_QUEU_PROCESS
WHERE MASTER_PROCESS_QUEUE_ID = @Pqid OR PARENT_PROCESS_QUEUE_ID = @Pqid
ORDER BY QUEUE_DT, PROCESS_QUEUE_ID;
```

Read: row count should match `CHILD_PROCESS_COUNT`. Large `wait_sec` is usually the job's own sequencing, not a QPEC pickup delay. Rerun a few minutes later: more finished children means progress.

## Q-L Orphan candidates (draft)

Rows that started, have no end date and are not in PRC. Use the dashboard Status reference to decide which statuses are terminal; a terminal status with no end date is an orphan, while waiting statuses are legitimately in flight.

```sql
SELECT STATUS_CD, PROCESS_ID, LOCAL_MACHINE_ID, CAST(START_DT AS date) AS start_day, COUNT(*) AS rows_n
FROM QARCH_QUEU_PROCESS
WHERE START_DT IS NOT NULL AND END_DT IS NULL AND STATUS_CD <> 'PRC'
  AND START_DT >= DATEADD(DAY, -30, GETDATE())
GROUP BY STATUS_CD, PROCESS_ID, LOCAL_MACHINE_ID, CAST(START_DT AS date)
ORDER BY start_day DESC, rows_n DESC;
```

## Q-M Abandoned work (draft)

Standing pile by process code, status and queued day:

```sql
SELECT PROCESS_ID, STATUS_CD, CAST(QUEUE_DT AS date) AS queued_day, COUNT(*) AS rows_n,
       MIN(ASSIGNED_MACHINE_ID) AS assigned_machine_example
FROM QARCH_QUEU_PROCESS
WHERE STATUS_CD IN ('BQU','QUE','SCH','WTP','PIK') AND QUEUE_DT < DATEADD(DAY, -7, GETDATE())
GROUP BY PROCESS_ID, STATUS_CD, CAST(QUEUE_DT AS date)
ORDER BY queued_day DESC, rows_n DESC;
```

Newly abandoned (queued between 7 and 8 days ago, the rows crossing the line now):

```sql
SELECT PROCESS_ID, STATUS_CD, COUNT(*) AS rows_n, MIN(QUEUE_DT) AS first_queued, MAX(QUEUE_DT) AS last_queued
FROM QARCH_QUEU_PROCESS
WHERE STATUS_CD IN ('BQU','QUE','SCH','WTP','PIK')
  AND QUEUE_DT >= DATEADD(DAY, -8, GETDATE()) AND QUEUE_DT < DATEADD(DAY, -7, GETDATE())
GROUP BY PROCESS_ID, STATUS_CD
ORDER BY rows_n DESC;
```

Assignments pointing at machines that are not QPEC servers:

```sql
SELECT ASSIGNED_MACHINE_ID, COUNT(*) AS rows_n
FROM QARCH_QUEU_PROCESS
WHERE STATUS_CD IN ('BQU','QUE','SCH','WTP','PIK') AND ASSIGNED_MACHINE_ID IS NOT NULL
GROUP BY ASSIGNED_MACHINE_ID;
```

Compare the result with the machine names in Q-F.

## Q-N Messages for a run or window (adapted; the per-run message tables returned no rows for a hung run)

Run early: logs are purged.

```sql
SELECT TOP 300 LOG_ID, LOCAL_MACHINE_ID, PROCESS_QUEUE_ID, LOG_MSG_TYPE_CD, LOG_DATE, LOG_MSG
FROM QARCH_QPEC_MSG_LOG
WHERE LOG_DATE >= @Start AND LOG_DATE < @End
ORDER BY LOG_DATE;

SELECT * FROM QARCH_PROCESS_MSG_LOG WHERE PROCESS_QUEUE_ID = @Pqid ORDER BY 1;
SELECT * FROM QARCH_STG_PROCESS_MSG_LOG WHERE PROCESS_QUEUE_ID = @Pqid;
```

Read: empty message tables for a long-running job mean it wrote nothing, which on its own does not prove a hang. Also check the per-run log file on the QPEC server (powershell-checks.md, PS-1).

## Q-O Peak concurrent jobs per QPEC server (adapted)

```sql
SELECT a.LOCAL_MACHINE_ID, MAX(x.running) AS peak_running
FROM QARCH_QUEU_PROCESS a
CROSS APPLY (
    SELECT COUNT(*) AS running
    FROM QARCH_QUEU_PROCESS b
    WHERE b.LOCAL_MACHINE_ID = a.LOCAL_MACHINE_ID
      AND b.START_DT <= a.START_DT
      AND (b.END_DT IS NULL OR b.END_DT > a.START_DT)
) x
WHERE a.START_DT >= @Start AND a.START_DT < @End
GROUP BY a.LOCAL_MACHINE_ID
ORDER BY peak_running DESC;
```

Read: compare with the number of QPEC instances on that server. Rows with no end date inflate the count; exclude old dead rows by keeping the window tight.

## Q-P For a DBA (L2 normally cannot run these)

The DMVs need VIEW SERVER STATE, which L2 logins have not had (Msg 300 "VIEW SERVER STATE permission was denied"). Hand these to a DBA with the QPEC server name, the job start time, and the QFC database name. Sessions disappear when the QPEC process is killed, so ask for them before the kill.

SQL Server (sessions from the QPEC host, open transactions, waits and blocking):

```sql
SELECT s.session_id, s.status, s.login_time, s.last_request_start_time, s.last_request_end_time,
       s.host_name, s.program_name, s.login_name, s.open_transaction_count, s.cpu_time, s.logical_reads
FROM sys.dm_exec_sessions s
WHERE s.database_id = DB_ID('REPLACE_QFC_DB') AND s.session_id <> @@SPID
ORDER BY s.last_request_start_time;

SELECT r.session_id, r.status, r.command, r.start_time, r.wait_type, r.wait_time, r.blocking_session_id,
       r.cpu_time, r.logical_reads, SUBSTRING(t.text, 1, 400) AS sql_text
FROM sys.dm_exec_requests r CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
WHERE r.database_id = DB_ID('REPLACE_QFC_DB') AND r.session_id <> @@SPID;
```

Read: a session from the QPEC host with `last_request_start_time` near the job start; running with growing reads is real work, blocked means find the head blocker, sleeping with `open_transaction_count` above 0 means it hung or died holding locks, no session means the row is orphaned.

Oracle (draft, untested; only if the QPEC process holds a connection to an Oracle server, and the DBA has access to `v$session`):

```sql
SELECT sid, serial#, username, status, machine, program, logon_time, last_call_et, event, sql_id
FROM v$session WHERE UPPER(machine) LIKE 'REPLACE_QPEC_HOST%' ORDER BY logon_time;
```

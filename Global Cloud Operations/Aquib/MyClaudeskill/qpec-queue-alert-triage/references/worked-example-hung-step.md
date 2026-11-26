# Worked example (anonymized): QpecJobRunningTooLong that was a hung step

Anonymized from a real first pass: no customer, user or host names, no addresses. It shows the order of checks and what changed the verdict, so use it as a pattern, not as the answer for the next alert.

## The alert

`QpecJobRunningTooLong`, Sev2, one database: "1 job(s) ... in PRC for more than 4 hours with no end time". First responders found services up and QPEC CPU and RAM under 30%, and noted the alert had fired before and "resolves by itself". No job was named.

## The checks and what each showed

1. Q-A listed five PRC rows. One was recent (about 20 hours at query time); four were months old. Verdict so far: the recent row is the alert; the old four are dead rows to note separately.
2. Q-B: the queue was moving (completed statuses updated minutes ago, one old `QUE` row). Not a stall.
3. Q-F: no QPEC instance claimed the recent row; all showed no active process. Alone this looked like an orphan, but one instance had not updated since the minute before the job started while every other instance had. That was a hint, not a conclusion.
4. Q-G: the job had three steps. Steps 1 and 2 finished within two seconds; step 3 was in PRC since then. The per-run message tables had no rows.
5. Q-H and Q-J: step 3 normally took 4 to 27 seconds (thousands of runs). Six runs ever had that step in PRC, and the five old and recent PRC rows were all stuck at step 3. So the step, not the job, was the pattern.
6. Q-I: the process normally completed in seconds (median 7 s, 95th percentile 14 s, longest 98 minutes). The open run was about 13 times the longest ever. Same-user runs of the same process kept finishing in seconds on both QPEC servers, so the process worked in general. All five stuck rows of that process were on one of the two QPEC servers (a question, not a conclusion).
7. PS-1: the per-run log file name gave a PID; the file was 0 bytes, last written at the job start.
8. PS-2: that PID existed, created the day before (so before the job), working set below the self-exit limit. The System Manager instance screen showed it ACTIVE on that process and step, disagreeing with the table in step 3.
9. PS-3: CPU moved 0.016 seconds in 60 seconds: idle.
10. PS-4, PS-5, PS-6: six connections; the SQL ones were mostly pooled from earlier. One connection to an Oracle-port endpoint on another server had been created in the same second the step started and was still open. Reverse DNS failed; forward resolution of the likely host name matched. Other QPECs of other products held long-lived connections to the same server, so the connection alone proved nothing. A second QPEC of the same application had held one earlier and no longer did, consistent with release after a normal run.
11. Version (release dashboard): a 2021.10 build with no hotfixes consumed; a related fix in ADO existed only in later releases.
12. ADO search for the step name: a customer report of the same step hanging, never root-caused and closed in clean-up; other items where the step failed with timeouts (errors, not hangs).

## The verdict and what it asked for

"Consistent with a hung step in an idle QPEC process; root cause not determined." The next steps, in order: App Owner (what the step calls and why it uses that Oracle endpoint, whether the interface was down at the start time, whether the job can be killed and re-run safely, what ended the earlier 16-hour occurrence); DBA (session, wait and transaction data on both database servers, because L2 could not run DMVs, before the QPEC is killed); Engineering (analysis of the process dump taken, and whether a call timeout applies); then an approved STOP / KILL, with the row left to an approved clean-up. A recurrence of this same step six times since May supported a problem record.

## What made the difference

- Reading every PRC row, not just the first.
- Looking at the step, not only the job: a step baseline turned "a long job" into "an abnormal step".
- Checking the process on the server (age, CPU, connections, log) rather than trusting the alert's "genuinely executing" text or one table.
- Not stopping at "an open connection": comparing it with what healthy processes do.
- Writing what was not known, and asking for the DBA data before the restart destroyed it.

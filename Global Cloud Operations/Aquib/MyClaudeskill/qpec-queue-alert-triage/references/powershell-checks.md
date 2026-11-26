# PowerShell checks on the QPEC / System Manager servers

Run on the server named in the alert's `system_manager` label (for example a `QC...CTX...` server), in PowerShell. All commands are read-only except the dump (PS-9) and the System Manager actions, which have a gate in escalation.md. Print file paths only when searching config files: config lines can contain credentials.

Proof status: PS-1 to PS-5, PS-6, PS-7 were run on a real case. PS-8, PS-10 are adapted from the investigation guide. PS-9 is a standard technique, not run in a case.

Contents: PS-1 find the per-run log and PID, PS-2 process exists and age, PS-3 CPU sample, PS-4 connections with age, PS-5 resolve and test endpoints, PS-6 who else uses the same endpoint, PS-7 log state, PS-8 self-shutdown signature, PS-9 dump, PS-10 Windows events for a DB or VM stall.

## PS-1 Find the per-run log and the PID

The QPEC log folder is environment-specific. A typical layout is `<drive>:\Quorum\<ENV>\QPEC\<app>\Logs`. If you do not know it, list QPEC processes (PS-2) and look at their location, or ask the App Owner.

```powershell
Get-ChildItem "<QPEC log root>" -Recurse -Filter "*<PROCESS_QUEUE_ID>*" | Select-Object FullName, Length, LastWriteTime
```

A hit named `RealTimeMsgLog_<PROCESS_ID>_<PID>_<PROCESS_QUEUE_ID>.log` gives the PID of the QPEC process that took the job. The log's size and last write time show whether the job wrote anything: a 0-byte file last written at the job start means no output since.

## PS-2 Does the process exist, and is it older than the job

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId=<PID>" | Select-Object ProcessId, Name, CreationDate, WorkingSetSize
Get-CimInstance Win32_Process -Filter "Name like 'qpec%'" | Select-Object ProcessId, Name, CreationDate | Sort-Object CreationDate
```

Read: no process with that PID, or a `CreationDate` after the job's `START_DT`, means the worker that took the job is gone (dead row; Windows can reuse PIDs, so compare the time). A process created before the job and still present means it may still hold the job. The process name carries the application and environment (`QPEC_<APP>_<ENV>.exe`), which confirms you are looking at the right one. QPEC self-exits when its memory passes about 750 MB and restarts automatically about 15 seconds later; compare `WorkingSetSize`.

## PS-3 CPU sample

```powershell
$a = Get-Process -Id <PID> | Select-Object CPU, WS, @{n='Threads';e={$_.Threads.Count}}
Start-Sleep 60
$b = Get-Process -Id <PID> | Select-Object CPU, WS, @{n='Threads';e={$_.Threads.Count}}
$a; $b
```

Read: `CPU` is cumulative seconds. A change of a fraction of a second in 60 seconds is idle. A job doing real work moves it by seconds. Idle CPU alone does not prove a hang (a job can be waiting on a long database call), but combined with an empty log and a step far beyond baseline it points that way.

## PS-4 Connections of the process, with age

```powershell
Get-NetTCPConnection -OwningProcess <PID> -State Established |
  Select-Object LocalPort, RemoteAddress, RemotePort, CreationTime | Sort-Object CreationTime
```

Read: connections created at the job's start time and still open belong to the job. Older ones are pooled connections from earlier work. Note every remote address and port.

## PS-5 Name the remote endpoints and test them

```powershell
Resolve-DnsName <RemoteAddress>
Resolve-DnsName <ServerName> | Select-Object Name, IPAddress
Test-NetConnection <RemoteAddress> -Port <RemotePort>
```

Read: a reverse lookup may fail; resolve the likely host name forward and compare IPs. Port 1521 is the default Oracle listener port; a named SQL Server instance usually listens on a high dynamic port. `TcpTestSucceeded False` means the endpoint is not reachable from this server now, which is relevant to a hang. The test opens its own short connection and does not touch the process's.

## PS-6 Who else holds connections to the same endpoint

```powershell
Get-NetTCPConnection -RemotePort <RemotePort> | ForEach-Object {
  $p = Get-CimInstance Win32_Process -Filter "ProcessId=$($_.OwningProcess)"
  [pscustomobject]@{ Pid=$_.OwningProcess; Name=$p.Name; Remote=$_.RemoteAddress; State=$_.State; Created=$_.CreationTime }
} | Sort-Object Name, Created | Format-Table -AutoSize
```

Read: if other QPECs (other products) hold long-lived connections to that endpoint, an open connection by itself is not evidence of a wait. If healthy QPECs of the same application hold none (they open and release it per run), a connection held for many hours stands out. Compare before and after a normal run if you can.

## PS-7 Search config files for a host or IP (paths only)

```powershell
Get-ChildItem "<QPEC root>" -Recurse -Include *.config,*.ini,*.xml -ErrorAction SilentlyContinue |
  Select-String -Pattern '<host or IP>' -List | Select-Object Path
```

`-List` with `Select-Object Path` prints only file names. Do not print the matching lines.

## PS-8 Self-shutdown signature (QPEC exited because it could not read the queue)

```powershell
Select-String -Path "<QPEC log root>\qpec_*.log" -Pattern 'This QPEC instance will be shut down immediately' -List | Select-Object Path
```

Read: the log lines before it are `query failed: m_Sel_Qarch_Queu_Process_Top` and `This is a serious problem - [bQueuedProcessExists = true] but [pQueuedProcess = NULL]`. It means the QPEC could not read the queue (typically the database was unreachable) and exited by design. Note the time and how many QPECs logged it. The matching helper script in the team's script library can search for this across logs.

## PS-9 Process dump (evidence for Engineering)

Only with the gate in escalation.md, and before any STOP or KILL. Either Task Manager (Details tab, right-click the process, Create dump file) or a dump tool the team uses, writing to a folder with restricted access. The dump contains process memory, possibly credentials and customer data: do not attach it to ADO, do not leave it on a shared folder, and record the path and time in the comment. Dumps of a busy QPEC are hundreds of MB.

## PS-10 Windows events around a database or VM stall (times in UTC)

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime='<UTC start>'; EndTime='<UTC end>'} |
  Where-Object { $_.Id -in 1,1074,5719,7009,7011 } | Select-Object TimeCreated, Id, ProviderName, Message
```

Read (run on the SQL server): Kernel-General 1 with a few minutes of jump means the VM was paused and the clock stepped forward; 7009 or 7011 are service timeouts; 5719 no domain controller; 1074 a planned restart. SQL or disk errors being absent alongside these points to the host or VM layer, which is for infra, not the DBA. Convert UTC to local before comparing with queue times.

## System Manager actions (not PowerShell)

STOP, then KILL if the QPEC does not stop, then START, in System Manager per QPEC instance. The action history lists who did what and when; automatic restarts by System Manager appear only in `SystemManagerService.log`. Gate and sequence: escalation.md.

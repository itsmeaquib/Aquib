# Worked example: eONE UAT crash-loop (QCUAUXE1MT501)

This is the analysis that set the house style, re-rendered with the skill's rules applied.
Read it to calibrate level of detail and to see how gaps are handled. Facts come from the
original analysis; items the original did not source are marked so, rather than asserted.

---

**Log analysis: eONE service crash-looping (QCUAUXE1MT501)**

*AI-assisted analysis, advisory only - pending human review. All times CDT. Logs in CDT.*

**Status as of <posting date/time CDT>:** the original analysis said "weekend deadline" and
"today's refresh" (written Oct 9). Replace with absolute dates and check whether the service
has since been fixed before posting.

**Verdict:** eONE will not start because the application build is newer than the database after
the UAT DB refresh (WI #1888642) | **Confidence:** High on cause (exact error + trigger +
precedent); Medium on the recommended fix until engineering confirms the version ordering.

**Root cause**
After the UAT DB refresh, the database is at 8.2026.03.SP2.207 while the application is at
8.2026.03.SP3.205. eONE refuses to connect when the app version does not match the DB, so
`EnteroServer` never starts and the YAJSW wrapper gives up.

**Key evidence**
- Exact error [Log: service log]: `InvalidDatabaseException: The eONE application version is 8.2026.03.SP3.205 and the database is 8.2026.03.SP2.207. You cannot connect.`
- Pattern [Log]: 165 occurrences of the exception across 4 start attempts. Show the arithmetic
  from `log_facts.py` (e.g. "N cycles x M lines per cycle"). The original said only "165" - a
  reader cannot tell if that reconciles with 5 wrapper restarts per attempt, so decompose it.
- Wrapper [Log]: exit code 999 on each attempt, then "too many restarts: 5". Code 999 is the
  wrapper's generic failure code - it reflects the app failing to start, not a separate fault.
- Not found [Log]: no "Started EnteroServer" on Oct 9; no other startup errors.

**Environment**
QCUAUXE1MT501 (UAT), E:\QuorumApps\e-ONE\UAT\AUX-Sable, port 8888, Windows Server 2019,
Java 17.0.18, Oracle instance QCLD_AUX_E1_UAT. Customer: Aux Sable Liquid Products.

**Trigger**
UAT DB refresh from a PRD export dated 9/29 (WI #1888642) [ADO]. The export being SP2.207 is
[Inferred] from the error text - confirm from the export itself.

**Timeline (CDT)**
- ~15:10 - Citrix/UAT VM found stopped at EFI and started; original "Cannot start app" report [ADO]
- 15:43 - Customer user logged in to eONE successfully, so the app was healthy [Customer]
- 15:54 - Clean service stop (exit 0) for the refresh, matches "Service stopped" on #1888642 [Log/ADO]
- ~16:36 - Refresh complete, service start requested [ADO]
- 16:40 - First start fails with the version error; loops until wrapper gives up at 16:43 [Log]
- 17:14-17:32 - Three more start attempts, same failure [Log]

**Why it happened**
The UAT app has run SP3.205 since 2026-06-17 [source not cited in original - cite the change
ticket, version file, or earlier log]. The refresh loaded a PRD export at SP2.207, rolling the
DB back below the app version [Inferred from versions].

**Ruled out**
- Certificate Authority hypothesis (#1881385) in the AITriage block - the logs show a version
  check failure, not a TLS/CA error.

**Unrelated noise**
- Oct 5 Netty "Unsupported version" errors from 10.218.0.200 - likely scanner noise [Inferred];
  confirm the IP is a known scanner/monitor (Open items).

**Precedents**
- WI #1566509 (BHE E1 UAT) - same case (app newer than DB) - fixed by running `e1server.bat -m`
  from the E1 directory, then the service started normally.
- WI #1784208 - same case (comment) - app newer than DB is fixed with `e1server -m`; app older than
  DB needs a real upgrade.
- WI #1701311 (Suncor refresh) - reverse case - app was upgraded to match the DB. Not applicable
  here; it needs the opposite fix.

**Open items / unknowns**
- Why the VM was found stopped at EFI (~15:10) was not determined - host event, patching, or
  forced shutdown? It could recur.
- SP3.205 vs SP2.207: the service pack is newer but the build suffix is lower. Engineering/DBA
  must confirm which is actually newer before migrating.
- Source for "app on SP3.205 since 2026-06-17" and for the PRD export being SP2.207.
- Whether 10.218.0.200 is a known scanner.

**Next steps (ordered)**
1. Confirm version ordering | **Owner:** eONE engineering / DBA | **Risk:** wrong direction
   migration | **Depends on:** none
2. Back up/snapshot the UAT DB, then run `e1server.bat -m` from the E1 directory on
   QCUAUXE1MT501 and start the service | **Owner:** authorised UAT DBA/engineer | **Risk:** DB
   change; backup required | **Depends on:** step 1
3. Re-run the post-refresh script if required | **Owner:** Edward Baca (WI #1888642 is closed -
   re-engage) | **Depends on:** step 2 (migration first, then post-refresh script)
4. Update the customer (stated deadline in the original: "weekend" - convert to an absolute date)

**Verification:** "Started EnteroServer" in the service log, port 8888 listening, customer login
succeeds.
**Rollback / alternative:** if the migration fails, restore the pre-migration backup; if
engineering will not migrate forward, re-export from a PRD source that matches the UAT app
version.

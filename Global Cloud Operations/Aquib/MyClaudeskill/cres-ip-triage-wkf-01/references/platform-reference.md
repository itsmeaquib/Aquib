# Integration Platform Reference

Source: QuorumSoftware wiki, read 2026-11-03. Use this file for component roles, logs, identifiers, health, retry rules, escalation and ticket templates.

## Contents

- What the platform is
- Event path and components
- Identifiers
- Logs
- Health checks
- Retry and timeout rules
- Stalled events
- Escalation paths and ticket templates
- Support ticket process
- Diagnostic SQL (developer access)
- Legacy environments (22.4 and older)
- Wiki sources

## What the platform is

A set of .NET services that move business events between Quorum products (FLOWCAL, eSuite/TIPS, WellEz, OGsys, ProdOps, Landdox) for each customer tenant. It runs hosted (IPCH) or on-premises at the customer (IPOP). The troubleshooting steps are the same for both. Log and server access differs.

Key concepts: a **Tenant** is a customer. A **Subscription** is a tenant opting in to an event. An **Integration Profile** is a named set of flows. A **Flow Configuration** is the workflow template and mapping rules. A **Mapping** links an ID in one product to its ID in another.

## Event path and components

1. **Source product** sends the event. Absent in IP means the problem is on the source side.
2. **Services.Web** validates and publishes to RabbitMQ exchange `quorum-business.event`. Push errors are 400, 401, 403. It is the only service that writes to the core IPServicesDB tables.
3. **Event Classifier** re-publishes to `quorum-integration.event` with routing metadata. It caches tenant and configuration data for 60 seconds. Events with no activity record means it is down.
4. **Transport Listener** matches subscriptions in an in-memory cache, dispatches to the handler, retries 3 times with backoff, then dead-letters to `{eventSubscription}.error`. It reloads its subscription cache when Services.Web publishes a config change, so if it was down during a change it missed it. Stuck in "Processing" means stalled.
5. **Dispatch event (Orchestration.Controllers, DefaultController)** forwards to the Flow Engine.
6. **Flow Engine** is stateless. It runs the workflow template and calls back to Services.Web or Product Connectors during execution. Map errors mean the mapping step.
7. **Product Connectors** (stateless adapters, one per product) call the source product (`GetEntity`) or target product (`StoreEntity`).

Supporting services: **Service Registry** (service discovery, own database), **Health Monitor** (`/health-ui`), **Scheduler** (Hangfire timed jobs), **Messaging Monitor Worker** (persists activity records to `ActivityMessages` and `EventMessages`; unknown message types are silently dropped), **Bridge** (adapter for legacy systems), **Proactive Monitoring Admin** (alert configuration).

Components also call back into Services.Web. A failure that surfaces in the Flow Engine can start in Services.Web or a connector. Follow every call seen in a log to its destination even when it is not on the diagram.

## Identifiers

| ID | Header | Use |
| --- | --- | --- |
| Event ID | `x-event-id` | Follows one business event through every service. Also the key in the activity grid and `IP.ActivityMessages` |
| Correlation ID | `x-correlation-id` | Ties together one request. Present in every `QResponse` body and every log entry |
| Stack trace | `X-Troubleshooting-Info` response header | Holds the full exception stack trace when present |

## Logs

Each service writes to `{AppRoot}\logs\{stem}{yyyymmdd}.log` under its IIS application root, for example `Quorum.IntegrationPlatform.Services.Web20260612.log`.

| Component | Log file stem |
| --- | --- |
| Services.Web | `Quorum.IntegrationPlatform.Services.Web` |
| Event Classifier | `Quorum.IntegrationPlatform.EventClassifier` |
| Transport Listener | `Quorum.IntegrationPlatform.Orchestration.TransportListener` |
| Dispatch (Default Controller) | `Quorum.IntegrationPlatform.Orchestration.Controllers` |
| Flow Engine | `Quorum.IntegrationPlatform.Orchestration.FlowEngine` |
| Product Connectors | `Quorum.IntegrationPlatform.ProductConnectors` |
| Messaging Monitor Worker | `Quorum.Messaging.Monitor.WorkerService` |
| Service Registry | `Quorum.IntegrationPlatform.ServiceRegistry` |
| Health Monitor | `Quorum.IntegrationPlatform.HealthMonitor` |
| Scheduler | `Quorum.IntegrationPlatform.Scheduler` (job output is in the Hangfire dashboard) |
| Bridge | `Quorum.IntegrationPlatform.Bridge` |
| Proactive Monitoring Admin | `Quorum.IntegrationPlatform.ProactiveMonitoringAdmin` |

Other logs:

- **IIS access logs**: `%SystemDrive%\inetpub\logs\LogFiles\W3SVC{SiteId}\u_ex{YYMMDD}.log`. Show whether a request reached the server at all, which matters for 502 and 503 errors that never reach the application.
- **IIS stdout logs**: `{AppRoot}\logs\stdout_{timestamp}_{pid}.log`. Capture a service that fails to start. Off by default (needs a `web.config` change, `stdoutLogEnabled="true"`) so ask developers. Turn it off afterwards because it creates a file per process start.
- **RabbitMQ**: management UI (port 15672) under Admin, Log Files, or `%APPDATA%\RabbitMQ\log\rabbit@{hostname}.log` on the server.
- **Hangfire**: stored in the Hangfire database. Dashboard at `http://{scheduler-host}/dashboard`.

Notes: file logging is off by default, so if no files appear check that `EnableFileLogging` is true in the deployed `appsettings.OnPrem*.json` (the template placeholder is `{{IntegrationPlatform.EnableFileLogging}}`). Logs roll daily and at 10 MB and only the last 10 files are kept, so older evidence may be gone.

## Health checks

Dashboard: `http://[server-name]/health-ui`, or IP UI, Monitoring, Health. Health Monitor polls every 30 seconds and does not re-notify for the same failure within one day.

Endpoints: `/health` (full), `/core` (database and broker), `/ipservices` (Services.Web), `/orchestrationservices` (Transport Listener, Flow Engine, Scheduler), `/productconnectors`, `/rabbitmqcluster`.

IP also health-checks connected target products every 30 seconds and stops delivering to a target it sees as down. Events sent in the gap before detection fail with "event cannot be delivered" and need republishing.

## Retry and timeout rules

| Policy | Setting |
| --- | --- |
| Service-to-service HTTP | Overall timeout 5 minutes, per-try timeout 2 minutes, jittered exponential backoff with a 10-second base |
| Circuit breaker | Opens at 50% failure rate over 30 seconds with at least 10 requests, stays open 5 seconds, then half-open. Watches 5xx, timeouts and 429 |
| Services.Web publishing to RabbitMQ | 3 retries, 1 second plus jitter |
| Transport Listener dispatch | 3 retries with backoff, then dead-letter to `{eventSubscription}.error` |

Because of backoff, one failure leaves several log lines at each layer. The first one matters. If the overall timeout fires before per-try retries finish, the retry never gets a chance to heal the request.

## Stalled events

Confirm a stall only when **all four** are true: events show no status or permanent "Processing"; no new messaging activity in the last hour; a clear timestamp cutoff in event history; RabbitMQ queues accumulating messages.

Health message when Transport Listener is down: "not connected to RabbitMQ or number of channels is less than expected. Expected: 3".

| Time after stall | Observable effect |
| --- | --- |
| 0 to 30 seconds | Health check turns Unhealthy |
| 1 to 5 minutes | RabbitMQ queues start accumulating |
| 5 to 10 minutes | First user reports of missing data |
| 10+ minutes | Circuit breaker may trip, holding queue fills |
| 30+ minutes | Multiple integration failures, widespread impact |

Common on-premises causes: network interruption to RabbitMQ; RabbitMQ restart without Transport Listener recovering; firewall change blocking port 5672; configuration reload failure; expired certificates or credentials; memory or CPU exhaustion; destination system failure opening the circuit breaker.

Developer-only verification: RabbitMQ management UI (queue growth, Transport Listener connection "running" with 3 active channels); Transport Listener logs (last successful message, disconnects); Windows Service status and CPU use (a stalled service shows minimal CPU); network reachability to RabbitMQ on port 5672.

Expected durations: symptom identification under 15 minutes, developer verification 15 to 30 minutes, a service restart 5 to 10 minutes (by developers or Cloud Ops), backlog processing 10 to 60 minutes, 1 to 2 hours total on average.

## Escalation paths and ticket templates

**Stalled events**

1. 0 to 15 minutes, Support: verify symptoms, check health dashboard, record start time and recent changes.
2. Within 30 minutes, email the developers at `q.integration.platform.point@quorumsoftware.com` with client name and ID, environment (QCloud or on-premises), application server name, screenshots, approximate start time and recent changes.
3. No developer response within 1 hour: open a Cloud Ops support ticket.

Cloud Ops ticket template from the wiki:

```
Title: Integration Platform - Event Processing Stalled - [CLIENT NAME]
Event processing is stalled in production for [Client Name/Identifier].
- Data synchronization has stopped
- Customers will not see up-to-date data in TIPS
- No Integration Platform activity visible to users
- Users are unaware of processing failure
Server: QCP[CLIENT-ID]IPZA01 (adjust as needed)
Impact: HIGH - No data processing occurring
Time Noticed: [TIMESTAMP]
Category: Service Disruption
Sub-Category: Application
Cloud: QCloud
Environment: PRD
Product: Integration Platform
Area: myQuorum Cloud\Global Cloud Operations\Incidents
Iteration: myQuorum Cloud\Global Cloud Operations
```

The wiki template also lists Cloud Platform "QCloud 1.5". That field has a restricted allowed-value list in Azure DevOps, so confirm the exact dropdown value with the user or leave it blank. Do not type it blindly.

**Who owns what**

| Situation | Escalate to |
| --- | --- |
| Stalled events, many tenants, health red, classifier or router stopped | Integration Practice developers (email), then Cloud Ops after 1 hour without response |
| Target product down and later events keep failing | Cloud Ops incident |
| Mapping missing or wrong | Customer Support task (error, products, data ID, event link, screenshot) |
| Resource missing in a target product | Products team |
| Source product sends bad data | Customer or the source product's data owner |
| Flow or tenant configuration change needed | Integration Practice support or developer |
| Error IP cannot fix (AfeType, unknown vendor ID) | The owning product team |

During an active incident, do not restart services, delete RabbitMQ messages or edit configuration files without developer or Cloud Ops approval.

## Support ticket process

Create a task in Azure DevOps with: requestor, environment, source product, target product, entity ID, issue description with screenshot and error code, priority or due date. The Support Queue Admin checks the queue daily, assigns it (or delegates by knowledge), reports it at daily stand-up and tags it IP, Support, client name. The assignee asks the requestor for missing details and sets Blocked = yes with a comment while waiting, then unblocks, schedules by priority, and keeps the requestor informed. On closing, describe the resolution and main root cause in a comment, then ask the requestor to validate. If not validated, reopen. A further request becomes a separate task.

## Diagnostic SQL (developer access, database IPServicesDB, schema IP)

```sql
-- Most recent 100 messages
SELECT TOP 100 Id, EventId, SentTime, Status, ValidationMessages FROM [IP].ActivityMessages ORDER BY SentTime DESC;

-- Failures in the last 24 hours
SELECT Id, EventId, SentTime, Status, ValidationMessages FROM [IP].ActivityMessages
WHERE Status != 'Success' AND SentTime >= DATEADD(HOUR, -24, GETUTCDATE()) ORDER BY SentTime DESC;

-- One event
SELECT * FROM [IP].ActivityMessages WHERE EventId = '{event-id}' ORDER BY SentTime;

-- Tenant profile assignment
SELECT t.TenantId, t.Name, ip.ProfileId, ip.Name AS ProfileName
FROM [IP].TenantIntegrationProfiles tip
JOIN [IP].Tenants t ON t.Id = tip.TenantId
JOIN [IP].IntegrationProfiles ip ON ip.Id = tip.IntegrationProfileId
WHERE t.TenantId = '{tenant-id}';

-- Mappings for a tenant
SELECT TenantId, ProductId, Entity, EntityId, AdditionalKeys FROM [IP].Mappings
WHERE TenantId = '{tenant-id}' ORDER BY Entity, EntityId;

-- Subscriptions for a tenant
SELECT s.Id, s.TenantId, se.EventId, se.ProductId FROM [IP].Subscriptions s
JOIN [IP].SubscriptionEvents se ON se.SubscriptionId = s.Id WHERE s.TenantId = '{tenant-id}';
```

These are read-only SELECTs. Never suggest data-changing SQL.

## Legacy environments (22.4 and older)

Logs are one undated file per service with times but no dates, so use the file's last-modified date for the day. Inbound API traffic passes through **WSO2 Micro Integrator** (a Windows service, not an identity provider). Logs: `{MI_HOME}\repository\logs\wso2-mi.log` (main), `audit.log`, `http_access_.log` (every inbound request, equivalent to the IIS access log). A 503 from the Micro Integrator means the backend is unreachable, so confirm the platform service is running and the endpoint config points at the right host.

## Wiki sources

All in the QuorumSoftware wiki in Azure DevOps (`https://quorumsoftware.visualstudio.com/QuorumSoftware/_wiki/wikis/QuorumSoftware.wiki`), read 2026-11-03:

- Integration Platform: Problem Triage (page 15202)
- Integration Practice (page 38)
- App Expert Guide, path `/QuorumSoftware/Integration Practice/Integration Platform/Operational Support/App Expert Guide`
- Common Errors in Integration Platform, Stalled Events Runbook, Bulk Event Republish, and IPCH Activity Messages Troubleshooting, under `/QuorumSoftware/Integration Practice/Process Guidance/Maintenance & Support/Troubleshooting knowledge base/`
- Maintenance & Support, path `/QuorumSoftware/Integration Practice/Process Guidance/Maintenance & Support`

Bulk Event Republish: filter **ActualErrorsByEventId** to find events still broken (latest unsuccessful activity per target). AllErrorsByEventId can be outdated if a later activity succeeded. Other filters: Date (default last 1 hour), Display name, Description contains, Event ID, Event type, Status, Tenant, Source product, Target product, and the LastActivityBy* and BestStatusByEventId views. Filters are saved in the page URL, so paste the link in the ticket. Select activities and click REPUBLISH EVENTS. Try one event first.

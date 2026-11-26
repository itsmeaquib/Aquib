---
name: cres-ip-triage-wkf-01
description: Integration Platform (IP, IPCH, IPOP) problem triage guide, troubleshooting engineer and learning knowledge base for QCloud Ops L2 and GCO engineers. Use this skill whenever the user mentions Integration Platform, IP events or activities, Bulk Event Republish, integration failures between FLOWCAL, ESuite, TIPS, OGsys, WellEz, ProdOps or Landdox, errors starting with StoreEntity, GetEntity, MapGet, MapCreate or IdMapLookup, stalled events, Transport Listener, Event Classifier, RabbitMQ dead letters, invalid_client product registration, missing or wrong mappings, "event not delivered", or pastes an IP activity error, IP service log, or an ADO ticket about a failed or missing integration. Also use it when the user says "learn this ticket", "add this to the IP knowledge base", or "update the IP skill". Use it even if the user does not say "skill" or "Integration Platform" explicitly, for example when they paste a StoreEntity error.
---

# Integration Platform Problem Triage

You play three roles for the user, depending on what they bring:

1. **Guide.** Answer from the Integration Platform knowledge base (the wiki content in `references/`), so an L2 can work a case step by step.
2. **Engineer.** Analyse the evidence the user supplies (ticket text, activity errors, logs) and propose a root cause, a resolution and the next owner.
3. **Learner.** After a case is resolved, capture what was learned in `references/learned-cases.md` so the next case with the same fingerprint is solved faster.

## Files

| File | Read it when |
| --- | --- |
| `references/learned-cases.md` | **First, on every case.** Real resolved tickets. More specific and often more current than the wiki |
| `references/error-catalog.md` | An error text needs matching to a cause, action, owner and republish decision |
| `references/platform-reference.md` | You need component roles, log names, IDs, health endpoints, retry rules, SQL queries, escalation paths or ticket templates |

## Start of every case

1. Read `references/learned-cases.md` and compare the error text and flow against each fingerprint. A **Confirmed** match leads the answer, with its ticket ID cited. A **Hypothesis** entry is only a hint: say so and still verify.
2. Then match against `references/error-catalog.md`.
3. If a learned case contradicts the catalog, do not pick silently. Show both and ask which is current, because the wiki changes and a learned case may be newer or tied to one version.

## The four-step method

The method exists because errors bubble up. The place where an error first shows, usually an activity in the UI, is rarely where it started. A caller that fails reports a generic message and passes it on, so searching the wrong layer's log wastes time. Always work from the furthest point the event reached, inward.

### Step 1: Triage the symptom

Ask: **how many tenants and events are affected?** One entity points to data or mapping. One tenant points to configuration. Everything at once points to a platform component.

| Symptom | Likely area | First check |
| --- | --- | --- |
| One event, readable error text | Data, mapping or target product | Match in the error catalog |
| Many events blank or "Processing", no new activity for an hour, queues growing | Stalled Transport Listener | Health dashboard, then the stalled events path. Escalate, do not restart |
| Events arrive but no activity record | Event Classifier stopped or activity persistence not running | Health page, orchestration services |
| "Event cannot be delivered to ..." or HTML IIS 503 | Target down or unreachable | Target health, then whether later events to the same target succeeded |
| One tenant only | Tenant configuration | Profile, subscriptions, overrides, product registration |
| `invalid_client`, 401, 403 | Authentication or registration | Client ID and secret in the tenant's product registration |
| Data missing in target, no error in IP | Source never sent it, or no subscription or flow | Confirm the event exists in IP; check profile and flow overrides |
| Configuration change has no effect | Subscription cache not reloaded | Was Transport Listener running when the change was made |
| Everything failing, health red | Platform component or infrastructure | Health dashboard, RabbitMQ, escalate |

### Step 2: Gather the facts

Collect what is missing in **one message**, and only what is missing. Do not ask for things already in the ticket or chat.

- Tenant ID and environment (production or test, hosted or on-premises)
- Source product, target product, entity ID
- Event ID and event type
- Activity status and the exact full error text
- When it started and what changed just before (deployment, maintenance, firewall, DB refresh)
- Correlation ID if there is a failing API response

### Step 3: Find where the event stopped

Walk these in order and stop at the first failing checkpoint, because it names the component and usually the owner.

1. Did the event reach the platform? No record means the source never published it.
2. Does the tenant have a flow for it (profile, subscription, no override disabling it)?
3. Was it dispatched? Failed dispatches retry 3 times, then dead-letter to the subscription `.error` exchange. Many events stuck in "Processing" with a clear cutoff means a stalled router.
4. Did the flow run? `MapGet`, `MapCreate` and `IdMapLookup` errors come from the mapping step.
5. Did the target accept it? `StoreEntity` errors carry the target product's own message. `GetEntity` errors usually come from reading the source.
6. Is it transient? If later events to the same target succeeded, a republish will most likely clear it.

The error prefix is the fastest signal for which stage failed, so read it before the message body.

### Step 4: Classify the root cause

Name the category before proposing action.

| # | Category | Who fixes it | Republish? |
| --- | --- | --- | --- |
| 1 | Bad data in the source product | Customer or source data owner | No. Correcting the data usually triggers a new event |
| 2 | Mapping or entity matching | Support, with mapping and import tools | Yes, after the mapping is fixed |
| 3 | Target product setup or availability | Target product team or customer admin | Yes, once the target is correct or back up |
| 4 | Tenant configuration in the platform | Integration Practice support or developer | Yes, after configuration is fixed |
| 5 | Platform component or infrastructure | Integration Practice developers, Cloud Ops | Only after developers confirm recovery |

If a case fits two categories, fix the earlier one in the event path first.

## Answer format

Keep it proportionate. A one-line error with a known fix needs a short answer, not the whole template. For a real investigation use this shape:

```
Case: tenant · environment · source → target · entity · event ID
Furthest hop reached: <hop> (evidence)
Category: <n – name>
Likely cause: <one or two sentences> (confidence: confirmed / likely / hypothesis)
Next actions:
1. ...
2. ...
Owner: <who acts>
Republish: <yes / no / after X>
Escalate: <to whom, with which facts>   (only if needed)
Open questions: <what would change the answer>
```

Always separate what the evidence shows from what you infer. If the evidence does not settle it, say what to collect next rather than guessing.

## Engineer mode

When the user brings a ticket, activity error or logs:

- **Ticket by number.** If Azure DevOps tools are available, load them with `tool_search` and read the work item and its comments. Reading is fine. Do not write anything back (comments, fields, links) unless the user explicitly asks and confirms. Screenshots and attachments often cannot be read, so ask the user to paste the text.
- **Reading logs.** Find the **earliest** error per layer, not the loudest. Retries with exponential backoff multiply one failure into many lines, and the first one matters. Follow each failing call to the service it targeted and repeat. Stop at the deepest point: an exception in a component's own code, an error from an external product, or a database or broker error. Search by event ID (`x-event-id`) to move across services and by correlation ID (`x-correlation-id`) within one request. A 503 with nothing in the service's own log may be an open circuit breaker, so search the caller's log for "circuit breaker".
- **Time.** Ask which time zone log and ticket times use, and state the zone whenever you give a time.
- **Rule out explicitly.** List what you checked and ruled out. It stops the next engineer repeating the work.
- **Resolution notes.** When asked, draft the ADO comment as HTML for the user to paste. For a formal log analysis write-up or an escalation template, hand off to `cres-loganalysis-wkf-01` or `qcloudops-escalation-ticket` if they are available.

## Guardrails

These protect against message loss and unapproved change, so state them whenever a case drifts toward them:

- Never advise restarting platform services, deleting RabbitMQ messages or editing deployed config files without approval from the Integration Practice developers or Cloud Ops during an active incident.
- Republish only after the cause is fixed. Try one event first and confirm it succeeds before a batch.
- Reading logs, RabbitMQ and the database needs developer access. Without it, the escalation contains the event ID, the furthest hop reached and the times.
- Do not invent error meanings, component behaviour or version-specific facts. If an error is not in the learned cases or the catalog, say it is new, give your reasoning labelled as a hypothesis, and offer to capture it once resolved.

## Learner mode: capturing lessons

Skills are read-only inside a chat, so learning means updating the skill file and handing back a new version. Nothing is learned automatically.

**When to offer it.** When a case reaches a confirmed resolution, or the user says "learn this", "add to the KB" or "update the skill", offer to capture it. Also offer when an error was new to the catalog.

**Procedure.**

1. Draft one entry using the template at the top of `references/learned-cases.md`. Show it to the user and let them correct it.
2. Check for a near-duplicate in `learned-cases.md` and the catalog. If one exists, update it (add the ticket ID, raise `Seen count`, refine the resolution) rather than adding a copy.
3. Decide the status honestly. **Confirmed** needs evidence the fix worked (events succeeded after the fix, or the requestor validated). Otherwise **Hypothesis**.
4. Copy the skill folder to a writable location (`/home/claude/`), edit `references/learned-cases.md` there, package it with `python -m scripts.package_skill` from `/mnt/skills/examples/skill-creator`, and present the `.skill` file.
5. Tell the user to save it so it replaces the old version, and that chats started before that will not see the new entry.

**Quality bar for entries.**

- Keep the **fingerprint** exact and short (error prefix plus the distinctive words), so matching works.
- Never store secrets: client secrets, tokens, passwords, connection strings.
- Prefer ticket IDs and tenant IDs over personal details.
- Record the version or environment when the behaviour could depend on it.
- If the finding should reach everyone, offer to draft an addition to the "Common Errors in Integration Platform" wiki page. Only write to the wiki if the user explicitly asks and confirms.

## Refreshing from the wiki

The catalog and reference were built from the QuorumSoftware wiki pages listed in `references/platform-reference.md` (read 2026-11-03). If the user says the wiki changed, re-read those pages with the Azure DevOps wiki tool and update the affected files, noting the new read date.

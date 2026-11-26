# Integration Platform Error Catalog

Source: "Common Errors in Integration Platform", "IPCH Activity Messages Troubleshooting" and "Integration Platform: Problem Triage" wiki pages, read 2026-11-03. The `Cat.` column uses the root-cause categories from SKILL.md (1 bad source data, 2 mapping, 3 target setup or availability, 4 tenant configuration, 5 platform or infrastructure). A category marked *(inferred)* is not stated on the wiki.

Match on the error prefix first (`StoreEntity`, `GetEntity`, `MapGet`, `MapCreate`, `IdMapLookup`), then the distinctive words.

## Contents

- Republish usually fixes it
- Customer must fix the data, no republish
- Mapping or entity problems
- Target product setup
- Tenant configuration and platform

## Republish usually fixes it

| Error text contains | Cause | Action | Cat. |
| --- | --- | --- | --- |
| CommunicationException ... IQESUITEServiceWA; Unable to establish a connection with any endpoint; another user changed the record | Load and concurrency errors in the ESuite API. Retry logic has been added in ESuite | Republish. It should succeed | 3 |
| IIS 503 Service Unavailable (HTML page in the error) | Target unreachable or intermittent connectivity between IP and the target | If later events to the same target succeeded, it may be safe to ignore. Republish once connectivity is restored. If errors continue, open a Cloud Ops incident | 3 |
| The event cannot be delivered to 'ESuite-...' | Target was down and IP's 30-second health check had not noticed yet. Guaranteed Delivery logic kicked in | Republish when the target is back | 3 |
| GetEntity. Resource not found | FlowCal bug, often an inactive meter (fix expected in FlowCal 10.3.0.6) | Republish. If it fails again, check the data exists in the FlowCal environment | known FlowCal defect |
| GetEntity. No data found for provided query parameters | ProdOps is the target. TIPS may have sent a POSTED event before the close completed | Republish. If it fails, notify the Customer Support lead | 3 *(inferred)* |
| StoreEntity. One or more errors occurred | ESuite truncated several errors into one. Midstream engineering has a backlog item to add the details (task 1491779) | Search ADO for "One or more errors occurred" to find the true cause. A republish may work depending on that cause | 3 |

## Customer must fix the data, no republish

| Error text contains | Cause | Action | Cat. |
| --- | --- | --- | --- |
| StoreEntity. AnalysisDaily Meter ... does not exist in ESUITE | Data for a date not valid in ESuite. For one customer it was always bad year-2000 data from FlowCal; could also be wrong effective dates on the ESuite meter | Customer corrects the data | 1 |
| Exceeds maximum defined precision and/or scale (for example HvConvrsnDry, max precision 9, scale 5) | Value from FlowCal does not fit the ESuite column, often a mistyped heating value. FlowCal raised a validation exception | Customer corrects the value. A new IP event is triggered, so the failure can be ignored | 1 |
| GetEntity. Error parsing column ... PRESSURE | Pressure spike in the meter data (one case read 39116065406967900000000000000000000) | Customer fixes the data in FlowCal | 1 *(inferred)* |
| Value must be specified for CountryCode | Country entered as "United States" in FlowCal, so COUNTRY arrives as NULL. "USA" and "United States of America" work | Ask the customer to enter USA | 1 |
| Effective From Date cannot exceed Effective To Date | Known defect (work items 1610728 and 1540498) | Workaround: make characteristic edits in FlowCal to the end of the month. Often not possible for the customer | 1 or 3 |
| WellCode contains forbidden characters | A period in the well code (OGsys to WellEz). The error comes from the WellEz side | The responsible CSL team for the client fixes or recreates the entity in OGsys | 1 |

## Mapping or entity problems

| Error text contains | Cause | Action | Cat. |
| --- | --- | --- | --- |
| MapCreate. Failed to create mapping ... Confirm that the mapping use unique entities | A FlowCal meter number was changed. FlowCal has a roadmap item to publish a new event | Delete the existing mapping for the meter, then republish | 2 |
| MeterIdMapLookup. The system cannot find 'meter' mapping for target product 'ESuite' | Meter quantity or sample data sent for a meter with no FlowCal to ESuite mapping. Seen only as a direct result of the MapCreate failure | Correct the mapping as above, then republish | 2 |
| MapGet. The Mapping cannot be null | An update arrived before the entity existed in the target, or the entity was created before the target was integrated | If a later create event succeeded, ignore it. Republishing the old update can give a Landdox "Internal server error" (common Landdox behaviour, task 1531583). For a newly integrated tenant, import the entities with IP's import tool. Otherwise raise a task for Customer Support to create the mappings | 2 |
| WellIdMapLookup. Cannot find ... mapping for target product ... | Treated as a null mapping | Same as MapGet above | 2 |
| StoreEntity. The id in the request is not equal to the id specified in the URL | The Integration ID was changed in FlowCal after the meter was integrated and mapped. Changing integration IDs is not supported | Resolve the IP ID mapping, then republish if needed | 2 |

For a mapping task to Customer Support, include the error, source product, target product, data ID, a link to the event and a screenshot. Example title: "Mappings cannot be null. Source ogsys. Target wellez, landdox, prodops. Id 645".

Older IP versions without mapping tools: fix mappings with the Postman mapping collection attached to the Common Errors wiki page. It needs the base IPSERVICES URL, tenant ID, source and destination meter IDs and a bearer token from a high-access account. It is set up for FlowCal to ESuite by default.

## Target product setup

| Error text contains | Cause | Action | Cat. |
| --- | --- | --- | --- |
| Plant Company does not match with Contract Company | The company on the TIPS plant (Facility Definition) differs from the company on the shared meter (ESUITE or TIPS Shared Meter). Several effective date ranges may each have a different company | Make every date range in the shared meter match the facility company. If TIPS is correct, check ESuite tables SCTRL_ORG and SCTRL_CO_ADDRESS, which feed view SVALD_PLANT_HDR. Hierarchy is under ESUITE, System, Organization Maintenance | 3 |
| StoreEntity. AnalysisMonthly Meter ... does not exist in ESUITE | One of: gas analysis screen end-dated in TIPS; meter definition dates not aligned with staging table STRAN_ANALYSIS_MONTHLY; analysis tied to a different meter; analysis screen never set up | Fix the analysis setup in TIPS. The effective date must be open-ended | 3 |
| Contact '0' doesn't exist in the system | Shared meter has contact ID 0, which is invalid | A TIPS user assigns a valid contact, then the event should process | 3 |
| PUT request is forbidden from creating new Meters | A once-integrated meter was probably modified or deleted in eSuite, so the API tries to create it anew | Investigate the meter's state on the eSuite and TIPS side | 3 |
| StoreEntity. Resource is not registered for the product and tenant | A required resource (for example BusinessAssociates) is missing for the product and tenant | Raise a task for the Products team to create the resource, then republish. Example title: "Missing resource BusinessAssociates. Source ogsys. Target prodops" | 3 *(inferred)* |
| StoreEntity. AfeType is required | OGsys sends no AFE type (afeType null) and WellEz requires one | Ask OGsys to return AfeType or WellEz to accept it empty. IP cannot fix this | 3 |
| StoreEntity. PRODUCT PUT: Unable to find vendor with id N | The sending product (for example PRODOPS) does not have that ID set up on its side, even though it looks like a mapping issue | The product's team adds the missing ID. Not fixable in IP | 3 |

## Tenant configuration and platform

| Error text contains | Cause | Action | Cat. |
| --- | --- | --- | --- |
| invalid_client (product registration) | Wrong Client ID or Client Secret in the tenant's destination product registration. Known issue: click Test connection before OK so the secret is saved | Correct the registration | 4 |
| Quorum Tenant was not found with given parameter(s) ...; Unable to find tenant information for ... | The integration flow is enabled for a product the tenant does not use | Tenants, open the tenant, INTEGRATION OVERRIDES tab, pick the profile (for example uod), find the flow, Action then Override with custom flow, remove the redundant target product, OK. Undo with Action then Restore default | 4 |
| Discover endpoint is not responding with code in 200...299 range, ServiceUnavailable | Seen on the IP Health page under orchestration services after firewall changes. The classifier service had status stopped, so events arrived without activity records | Developers or Cloud Ops start the service | 5 |

## Not in the catalog

If an error does not match anything here or in `learned-cases.md`, treat it as new. Classify it with the four-step method, label your reasoning as a hypothesis, and offer to capture it as a learned case once it is resolved.

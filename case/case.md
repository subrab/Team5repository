# Practice case: AI Friday Season 3 · Case A · Banking KYC

> Practice only. The organisers' reference D1, D2, D3 and D5 exist for this case, so we can calibrate our scores against them. On Friday, the team lead replaces this file with the real challenge.

## Business situation
A multi-channel bank handles about 30,000 new and periodic-review KYC cases per month across digital channels, branches and relationship managers. Around 20% of cases move to manual review because of missing documents, inconsistent customer data, screening alerts or policy exceptions.

The current process spans the onboarding application, CRM, core banking, document repository, AML/sanctions/PEP screening, workflow tools, email and analyst spreadsheets. Analysts frequently switch across several systems to reconstruct the case before deciding the next action.

| Current challenge | Business / delivery impact |
| --- | --- |
| Customer information and documents are captured differently across channels | Repeated checks, rework and inconsistent customer experience |
| Analysts must assemble evidence from multiple systems | Longer exception queues and high manual effort |
| Screening alerts and data mismatches are reviewed manually | Specialist capacity is consumed by routine investigation |
| Policy guidance is distributed across documents and knowledge portals | Inconsistent interpretation and slower onboarding |
| Decision evidence is fragmented | Audit preparation and root-cause analysis are difficult |

**Architecture question:** How should the bank modernize KYC exception handling and onboarding orchestration without replacing the core banking or screening platforms in Phase 1, while introducing AI safely and improving auditability, turnaround time and future channel integration?

## Constraints
- Core banking and the existing AML/sanctions screening platform remain in Phase 1.
- A 12-week pilot should cover one product / customer segment and a limited operating region.
- Customer PII, identity documents and bank-confidential data must stay within approved environments.
- AI must not make the final decision to approve/reject onboarding or dismiss a sanctions/PEP alert.
- AI-produced summaries or recommendations must be traceable to source information and reviewable by an analyst.
- Existing onboarding channels must remain usable when new services fail.

## Success measures
- Reduce avoidable manual handling for pilot cases by roughly 25-30%.
- Move common exception resolution toward same-day handling.
- Give analysts one case view with status, evidence and ownership.
- Capture the reason, evidence and human decision for every material case action.
- Make policy / rule changes easier to introduce without repeated channel changes.
- Create a governed path for additional AI-assisted onboarding capabilities.

## Deliverables (Seniors workbook): D1 Problem & success snapshot · D2 Architecture options & decision · D3 Target-state architecture · D4 Focused POC / validation · D5 Delivery & risk plan

## Possible jury changes
- Volume increases significantly. · A proposed technology is unavailable in Phase 1. · AI cannot receive identifiable or sensitive information. · The delivery timeline is reduced.

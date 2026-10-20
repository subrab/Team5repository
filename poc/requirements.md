Approved-by: Murali (practice example)
<!-- Requirement Clarifier agent output, reviewed by the Analyst. Practice case A (KYC). -->

## Business Objective
Prove that the Option B case layer keeps final KYC decisions and sanctions/PEP alert dispositions with authorized people, records every attempt, and keeps working when AI assistance is off.

## User Roles
KYC analyst; AML specialist; authorized approver; AI assistant (non-human); service account (non-human); screening system (non-human).

## Workflow
Case created from a channel → evidence check → (waiting for customer) → analyst review → (screening hold) → awaiting decision → decided by an authorized person.

## Data Inputs and Outputs
Input: case ID, idempotency key, actor (ID, role, human or not), action, reason, evidence references. Output: case state, accepted or refused, rule ID, audit entry with rules version.

## Business Rules
No decision with an open screening hold. Only an authorized human approver decides. Only an AML specialist clears a hold, with a reason. Systems may place a hold but never lift one or decide.

## Validations
Decisions need a reason and at least one evidence reference. Clearing a hold needs a reason.

## Exceptions
A screening alert can arrive at any open stage and must stop the case.

## Requirements
| REQ-ID | User story | Acceptance criteria |
| --- | --- | --- |
| REQ-001 | As an AML owner, I want no final decision while a screening hold is open, so that alerts are never bypassed | AC-001: Given a case with an open hold, when an authorized approver approves, then the action is refused with RULE-001 and the case stays on hold |
| REQ-002 | As a compliance owner, I want only an authorized human approver to make the final decision, so that AI and service accounts never decide | AC-002: Given a case awaiting decision, when an AI assistant, a service account or a human without the approver role approves, then it is refused with RULE-002 |
| REQ-003 | As an AML owner, I want only an AML specialist to clear a hold, with a reason, so that AI cannot dismiss alerts | AC-003: Given an open hold, when the AI or an analyst clears it, then it is refused; when a specialist clears it without a reason, then it is refused; with a reason, then the hold clears |
| REQ-004 | As an auditor, I want every decision and every refused attempt recorded, so that decisions can be reconstructed | AC-004: Given any action, when it is accepted or refused, then the audit trail holds actor, role, action, outcome, rule ID, reason, evidence and rules version |
| REQ-005 | As an operations lead, I want cases to complete with AI assistance switched off, so that an AI outage never blocks onboarding | AC-005: Given AI assistance disabled, when people work a case end to end, then it reaches DECIDED |
| REQ-006 | As an integration lead, I want a duplicate intake not to create a second case, so that case state never forks | AC-006: Given two intakes with the same idempotency key, when both arrive, then one case exists |
| REQ-007 | As an AML owner, I want a late screening alert to stop a case even after review, so that late hits are not missed | AC-007: Given a case awaiting decision, when an alert arrives, then the case moves to SCREENING_HOLD and approval is refused |

## Assumptions
ASSUMPTION A1: role and human/non-human identity come from the bank identity provider (simulated here). ASSUMPTION A2: the screening engine notifies alerts through an adapter (simulated here).

## Open Questions
Does the bank require maker-checker (two people) for approvals in the pilot segment?

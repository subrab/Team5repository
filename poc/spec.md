Approved-by: Subramaniabharathi (practice example)
<!-- Spec Generator agent output, reviewed by the Architect. -->

# Feature: Server-enforced human decision gate for KYC cases (D3 C-03, C-07, C-09)

## Business Objective
Enforce, on the server and from a versioned rules file, that only authorized people decide and only AML specialists clear screening holds, with every attempt audited and no dependency on AI.

## Actors
kyc_analyst, aml_specialist, authorized_approver (human); ai_assistant, service_account, screening_system (non-human).

## Workflow
1. WF-001: create case (idempotent) → NEW
2. WF-002: start_check → EVIDENCE_CHECK; request_evidence ↔ WAITING_FOR_CUSTOMER
3. WF-003: evidence_complete → ANALYST_REVIEW
4. WF-004: screening_alert (any open state) → SCREENING_HOLD; clear_hold → ANALYST_REVIEW
5. WF-005: submit_for_decision → AWAITING_DECISION
6. WF-006: approve / reject → DECIDED

## Specification
| SPEC-ID | Implements | Specification |
| --- | --- | --- |
| SPEC-001 | REQ-001 | approve / reject are refused while the case's screening hold is open |
| SPEC-002 | REQ-002 | approve / reject are allowed only for a human actor with role authorized_approver, with a reason and at least one evidence reference |
| SPEC-003 | REQ-003 | clear_hold is allowed only for a human aml_specialist with a reason |
| SPEC-004 | REQ-004 | every attempted action, accepted or refused, appends an audit entry with actor, role, kind, action, outcome, rule ID, reason, evidence and rules version |
| SPEC-005 | REQ-005 | no transition depends on the AI assistant; disabling it only disables suggestions |
| SPEC-006 | REQ-006 | case creation with an existing idempotency key returns the existing case |
| SPEC-007 | REQ-007 | screening_alert from any open state moves the case to SCREENING_HOLD and opens the hold; systems may place holds, never lift them |

## Functional Rules
- RULE-001 (implements SPEC-001): guard no_open_hold on approve / reject
- RULE-002 (implements SPEC-002): decision actor must be human authorized_approver; reason and evidence required
- RULE-003 (implements SPEC-003): hold clearance by human aml_specialist with reason
- RULE-004 (implements SPEC-004): audit every attempt
- RULE-005 (implements SPEC-005): AI assistance is optional and advisory
- RULE-006 (implements SPEC-006): idempotent intake
- RULE-007 (implements SPEC-007): late or early alert always places a hold

## Data Inputs and Outputs
Case: case_id, idempotency_key, state, hold_open. Actor: id, role, kind (human / ai / service). Result: ok, state, rule_id, message. AuditEntry: seq, case_id, action, actor_id, role, kind, outcome, rule_id, reason, evidence_refs, rules_version.

## Validations and Exceptions
- VAL-001: approve / reject need reason and evidence_refs. VAL-002: clear_hold needs reason.
- EXC-001: unknown action or action not allowed from the current state → refused, audited.

## Acceptance Criteria
- AC-001 (REQ-001) to AC-007 (REQ-007) as in the approved requirements.

## Traceability
- REQ-001 → SPEC-001 → CODE-001 → TEST-001
- REQ-002 → SPEC-002 → CODE-002 → TEST-002
- REQ-003 → SPEC-003 → CODE-003 → TEST-003
- REQ-004 → SPEC-004 → CODE-004 → TEST-004
- REQ-005 → SPEC-005 → CODE-005 → TEST-005
- REQ-006 → SPEC-006 → CODE-006 → TEST-006
- REQ-007 → SPEC-007 → CODE-007 → TEST-007

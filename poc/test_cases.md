Approved-by: Deepak (practice example)
<!-- Test Case Generator agent output, reviewed by the Tester. -->

## Test Cases
| TEST-ID | Type | REQ | AC | Given (synthetic data) | When | Then (expected) |
| --- | --- | --- | --- | --- | --- | --- |
| TEST-001 | Negative | REQ-001 | AC-001 | Case on screening hold | Authorized approver approves | Refused, RULE-001, stays on hold |
| TEST-002 | Negative | REQ-002 | AC-002 | Case awaiting decision | AI assistant (claiming approver role) approves | Refused, RULE-002 |
| TEST-008 | Negative | REQ-002 | AC-002 | Case awaiting decision | Service account rejects | Refused |
| TEST-009 | Negative | REQ-002 | AC-002 | Case awaiting decision | Human analyst (not approver) approves | Refused |
| TEST-010 | Boundary | REQ-002 | AC-002 | Case awaiting decision | Approver with no reason, or no evidence | Refused |
| TEST-003 | Negative + positive | REQ-003 | AC-003 | Case on hold | AI, analyst, specialist without reason, specialist with reason clear the hold | First three refused; last clears the hold |
| TEST-004 | Positive | REQ-004 | AC-004 | Case awaiting decision | AI attempt then human approval | Both in audit with actor, kind, rule ID, reason, evidence, version |
| TEST-005 | Integration | REQ-005 | AC-005 | AI assist disabled, alert raised | People clear hold, submit, approve | DECIDED; no suggestion produced |
| TEST-006 | Negative | REQ-006 | AC-006 | Two intakes, same idempotency key | Both arrive | One case |
| TEST-007 | Negative | REQ-007 | AC-007 | Case awaiting decision | Late screening alert, then approval | Hold placed; approval refused with RULE-001 |
| TEST-011 | Security | REQ-007 | AC-007 | Case on hold | Screening system tries to clear its own hold | Refused |
| TEST-012 | Regression | REQ-002 | AC-002 | Role added to approve in the DSL only | Senior analyst approves | Accepted, no code change |

## Coverage Summary
| REQ | Positive | Negative | Boundary | Other |
| --- | --- | --- | --- | --- |
| REQ-001 | 0 | 1 | 0 | 0 |
| REQ-002 | 0 | 3 | 1 | 1 regression |
| REQ-003 | 1 | 1 | 0 | 0 |
| REQ-004 | 1 | 0 | 0 | 0 |
| REQ-005 | 0 | 0 | 0 | 1 integration |
| REQ-006 | 0 | 1 | 0 | 0 |
| REQ-007 | 0 | 1 | 0 | 1 security |

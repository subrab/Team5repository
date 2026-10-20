# POC: spec-driven, traceable, built by an agent chain

Follows the AI Friday SPEC-Driven SDLC Best Practices: **Story → Spec → DSL → Code → Test → Review**, every piece linked by ID, with a human review gate between stages.

| Stage | Agent command | Owner (role) | Output | Human gate |
| --- | --- | --- | --- | --- |
| 0. POC question | (team decision) | Team | `notes/POC.md` | |
| 1. Requirements | `python iterate.py clarify` | Murali (Analyst) | `poc/requirements.md`: REQ-001..., AC-001... | `Approved-by:` line |
| 2. Specification | `python iterate.py spec` | Subramaniabharathi (Architect) | `poc/spec.md`: feature template, SPEC / RULE / VAL / EXC IDs, traceability | `Approved-by:` line |
| 3. YAML DSL | `python iterate.py dsl` | Muthuvel (Developer) | `poc/feature.yaml`, **schema-validated before handoff** | `Approved-by:` line |
| 4. Test design | `python iterate.py testcases` | Deepak (Tester) | `poc/test_cases.md`: positive, negative, boundary, integration, regression, security | `Approved-by:` line |
| 5. Code and tests | Kilo Code or Aider in VS Code, from the approved spec and DSL | Muthuvel, Deepak | `poc/src/`, `poc/tests/` | code review |
| 6. Review | `python iterate.py trace`, then `python iterate.py codereview` | Deepak | `TRACEABILITY.md`, `gaps/CODE-REVIEW.md` with readiness status | |

**Agent rules (from the Best Practices, section 6):** single responsibility per agent; strict input and output contracts (each agent's instruction file); schema validation before handoff (an agent that fails validation retries once, then its output is saved as `*.rejected.*` and nothing is handed on); traceability at every stage (IDs preserved; dropped IDs fail validation); human review gates for specification and architecture (the next agent refuses to run until the input has an `Approved-by:` line).

**ID conventions:** REQ-001 → SPEC-001 → RULE-001 (in the DSL) → CODE-001 (a comment in the code) → TEST-001 (in the test's docstring; test names start `test_REQ_001_...`).

**The worked example** is the D4 POC for practice Case A (KYC): a server-side human decision gate. 7 requirements fully traced, 12 tests passing (negative, boundary, integration, security, regression). Demo UI: `streamlit run poc/src/workbench.py`. On Friday, delete `requirements.md`, `spec.md`, `feature.yaml`, `test_cases.md`, `src/case_service.py`, `src/workbench.py` and the tests, and run the chain for the real POC. Keep `src/yaml_lite.py`.

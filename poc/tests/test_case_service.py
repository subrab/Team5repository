"""Tests named after the requirement they verify; TEST IDs in docstrings link them to the traceability matrix."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from case_service import CaseService  # noqa: E402

ANALYST = {"id": "u-anl-1", "role": "kyc_analyst", "kind": "human"}
SPECIALIST = {"id": "u-aml-1", "role": "aml_specialist", "kind": "human"}
APPROVER = {"id": "u-apr-1", "role": "authorized_approver", "kind": "human"}
AI = {"id": "ai-assist", "role": "authorized_approver", "kind": "ai"}          # even if it claims the role
SERVICE = {"id": "svc-batch", "role": "authorized_approver", "kind": "service"}
SCREENING = {"id": "svc-screening", "role": "screening_system", "kind": "service"}
EVIDENCE = ["DOC-PAN-001", "SCR-REF-77"]


def to_decision(svc, case_id="CASE-1", alert=False):
    svc.create_case(case_id, f"key-{case_id}", ANALYST)
    for a in ("start_check", "evidence_complete"):
        assert svc.act(case_id, a, ANALYST)["ok"]
    if alert:
        assert svc.act(case_id, "screening_alert", SCREENING)["ok"]
        return
    assert svc.act(case_id, "submit_for_decision", ANALYST)["ok"]


def test_REQ_001_no_decision_with_open_hold():
    """TEST-001 (negative, AC-001): approver cannot approve while the hold is open"""
    svc = CaseService(); to_decision(svc, alert=True)
    r = svc.act("CASE-1", "approve", APPROVER, "looks fine", EVIDENCE)
    assert not r["ok"] and r["rule_id"] == "RULE-001" and r["state"] == "SCREENING_HOLD"


def test_REQ_002_ai_cannot_decide_even_claiming_approver_role():
    """TEST-002 (negative, AC-002): AI assistant approval refused"""
    svc = CaseService(); to_decision(svc)
    r = svc.act("CASE-1", "approve", AI, "AI recommends approval", EVIDENCE)
    assert not r["ok"] and r["rule_id"] == "RULE-002" and r["state"] == "AWAITING_DECISION"


def test_REQ_002_service_account_cannot_decide():
    """TEST-008 (negative, AC-002): service account approval refused"""
    svc = CaseService(); to_decision(svc)
    assert not svc.act("CASE-1", "reject", SERVICE, "batch", EVIDENCE)["ok"]


def test_REQ_002_human_without_approver_role_cannot_decide():
    """TEST-009 (negative, AC-002): an analyst is human but not an approver"""
    svc = CaseService(); to_decision(svc)
    assert not svc.act("CASE-1", "approve", ANALYST, "ok", EVIDENCE)["ok"]


def test_REQ_002_decision_needs_reason_and_evidence():
    """TEST-010 (boundary, AC-002): approver without reason or evidence refused"""
    svc = CaseService(); to_decision(svc)
    assert not svc.act("CASE-1", "approve", APPROVER, None, EVIDENCE)["ok"]
    assert not svc.act("CASE-1", "approve", APPROVER, "ok", [])["ok"]


def test_REQ_003_only_specialist_with_reason_clears_hold():
    """TEST-003 (negative and positive, AC-003): AI and analyst refused; specialist needs a reason"""
    svc = CaseService(); to_decision(svc, alert=True)
    assert not svc.act("CASE-1", "clear_hold", {**AI, "role": "aml_specialist"}, "false positive")["ok"]
    assert not svc.act("CASE-1", "clear_hold", ANALYST, "false positive")["ok"]
    assert not svc.act("CASE-1", "clear_hold", SPECIALIST, None)["ok"]
    r = svc.act("CASE-1", "clear_hold", SPECIALIST, "DOB and nationality differ from list entry")
    assert r["ok"] and r["state"] == "ANALYST_REVIEW" and not svc.cases["CASE-1"]["hold_open"]


def test_REQ_004_every_attempt_is_audited_with_rule_and_version():
    """TEST-004 (positive, AC-004): refused and accepted attempts both in the audit trail"""
    svc = CaseService(); to_decision(svc)
    svc.act("CASE-1", "approve", AI, "AI recommends", EVIDENCE)
    svc.act("CASE-1", "approve", APPROVER, "evidence complete, no hits", EVIDENCE)
    refused = [e for e in svc.audit if e["outcome"] == "refused"][-1]
    accepted = svc.audit[-1]
    assert refused["kind"] == "ai" and refused["rule_id"] == "RULE-002" and refused["rules_version"] == "1.0"
    assert accepted["actor_id"] == "u-apr-1" and accepted["reason"] and accepted["evidence_refs"] == EVIDENCE


def test_REQ_005_case_completes_with_ai_switched_off():
    """TEST-005 (integration, AC-005): full path to DECIDED with AI disabled, including a hold"""
    svc = CaseService(ai_assist_enabled=False); to_decision(svc, alert=True)
    assert svc.ai_suggest("CASE-1") is None
    assert svc.act("CASE-1", "clear_hold", SPECIALIST, "false positive: different DOB")["ok"]
    assert svc.act("CASE-1", "submit_for_decision", ANALYST)["ok"]
    assert svc.act("CASE-1", "approve", APPROVER, "all checks complete", EVIDENCE)["state"] == "DECIDED"


def test_REQ_006_duplicate_intake_does_not_fork_case():
    """TEST-006 (negative, AC-006): same idempotency key twice gives one case"""
    svc = CaseService()
    a = svc.create_case("CASE-1", "key-X", ANALYST)
    b = svc.create_case("CASE-2", "key-X", ANALYST)
    assert a is b and len(svc.cases) == 1


def test_REQ_007_late_alert_stops_case_awaiting_decision():
    """TEST-007 (negative, AC-007): alert after review moves case to hold; approval refused"""
    svc = CaseService(); to_decision(svc)
    assert svc.act("CASE-1", "screening_alert", SCREENING)["state"] == "SCREENING_HOLD"
    assert svc.act("CASE-1", "approve", APPROVER, "ok", EVIDENCE)["rule_id"] == "RULE-001"


def test_REQ_007_systems_can_place_but_never_lift_a_hold():
    """TEST-011 (negative, AC-007): the screening system cannot clear its own hold"""
    svc = CaseService(); to_decision(svc, alert=True)
    assert not svc.act("CASE-1", "clear_hold", SCREENING, "auto-cleared")["ok"]


def test_REQ_002_rule_change_in_dsl_needs_no_code_change():
    """TEST-012 (regression, AC-002): adding a role in the DSL changes behaviour without code"""
    svc = CaseService(); to_decision(svc)
    svc.transitions["approve"]["roles"] = ["authorized_approver", "senior_analyst"]
    assert svc.act("CASE-1", "approve", {"id": "u-sa", "role": "senior_analyst", "kind": "human"}, "ok", EVIDENCE)["ok"]

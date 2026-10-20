"""KYC case service with a server-side human decision gate (D3 C-03 case registry, C-07 decision guard, C-09 audit).

Every transition, role and guard comes from feature.yaml (the DSL). The code enforces; the business owns the rules.
Implements SPEC-001 to SPEC-007.
"""
from pathlib import Path
import yaml_lite

DSL_FILE = Path(__file__).resolve().parent.parent / "feature.yaml"
RULE_REASON = {}


def load_dsl(path=DSL_FILE):
    return yaml_lite.load(Path(path).read_text(encoding="utf-8"))


class CaseService:
    def __init__(self, dsl=None, ai_assist_enabled=True):
        self.dsl = dsl or load_dsl()
        self.version = str(self.dsl["feature"]["version"])
        self.transitions = {t["action"]: t for t in self.dsl["transitions"]}
        self.rules = {r["rule_id"]: r for r in self.dsl["rules"]}
        self.ai_assist_enabled = ai_assist_enabled            # CODE-005: SPEC-005 / RULE-005, AI is optional
        self.cases, self.by_key, self.audit = {}, {}, []

    # CODE-006: SPEC-006 / RULE-006 - idempotent intake, one case per idempotency key
    def create_case(self, case_id, idempotency_key, actor):
        if idempotency_key in self.by_key:
            existing = self.by_key[idempotency_key]
            self._audit(existing, "create_case", actor, "duplicate-ignored", "RULE-006", None, None)
            return self.cases[existing]
        self.cases[case_id] = {"case_id": case_id, "idempotency_key": idempotency_key, "state": "NEW", "hold_open": False}
        self.by_key[idempotency_key] = case_id
        self._audit(case_id, "create_case", actor, "accepted", "RULE-006", None, None)
        return self.cases[case_id]

    def act(self, case_id, action, actor, reason=None, evidence_refs=None):
        """Attempt an action. Returns {ok, state, rule_id, message}. Every attempt is audited (CODE-004)."""
        case = self.cases[case_id]
        t = self.transitions.get(action)
        if t is None or case["state"] not in t["from"]:                        # EXC-001
            return self._refuse(case, action, actor, "EXC-001", f"'{action}' is not allowed from {case['state']}", reason, evidence_refs)
        # CODE-002 / CODE-003 / CODE-007: who may act is decided by the DSL, never by the caller
        if actor.get("kind") not in t.get("kinds", ["human"]) or actor.get("role") not in t["roles"]:
            return self._refuse(case, action, actor, t["rule_id"], self.rules[t["rule_id"]]["reason"], reason, evidence_refs)
        missing = [f for f in t.get("requires", []) if not (reason if f == "reason" else evidence_refs)]
        if missing:                                                            # VAL-001 / VAL-002
            return self._refuse(case, action, actor, t["rule_id"], f"missing {', '.join(missing)}", reason, evidence_refs)
        # CODE-001: SPEC-001 / RULE-001 - no decision while a screening hold is open
        if t.get("guard") == "no_open_hold" and case["hold_open"]:
            return self._refuse(case, action, actor, "RULE-001", self.rules["RULE-001"]["reason"], reason, evidence_refs)
        if t.get("opens_hold"):                                                # CODE-007: alerts always place a hold
            case["hold_open"] = True
        if t.get("closes_hold"):
            case["hold_open"] = False
        case["state"] = t["to"]
        self._audit(case_id, action, actor, "accepted", t["rule_id"], reason, evidence_refs)
        return {"ok": True, "state": case["state"], "rule_id": t["rule_id"], "message": "accepted"}

    def ai_suggest(self, case_id):
        """Advisory only: returns text, never changes state. Disabled means no suggestion, not a blocked case."""
        if not self.ai_assist_enabled:
            return None
        return f"Draft summary for {case_id} (cited evidence would appear here)."

    def _refuse(self, case, action, actor, rule_id, message, reason, evidence_refs):
        self._audit(case["case_id"], action, actor, "refused", rule_id, reason, evidence_refs)
        return {"ok": False, "state": case["state"], "rule_id": rule_id, "message": message}

    # CODE-004: SPEC-004 / RULE-004 - append-only audit of every attempt, accepted or refused
    def _audit(self, case_id, action, actor, outcome, rule_id, reason, evidence_refs):
        self.audit.append({"seq": len(self.audit) + 1, "case_id": case_id, "action": action,
                           "actor_id": actor.get("id"), "role": actor.get("role"), "kind": actor.get("kind"),
                           "outcome": outcome, "rule_id": rule_id, "reason": reason,
                           "evidence_refs": evidence_refs, "rules_version": self.version})

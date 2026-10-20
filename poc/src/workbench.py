"""Analyst workbench demo (D3 C-08) over the server-side decision gate. Run: streamlit run poc/src/workbench.py
Synthetic data only. The page calls CaseService exactly as a real UI would call the case API; it cannot bypass the gate."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import streamlit as st
from case_service import CaseService

ACTORS = {
    "Priya (KYC analyst)": {"id": "u-anl-1", "role": "kyc_analyst", "kind": "human"},
    "Arun (AML specialist)": {"id": "u-aml-1", "role": "aml_specialist", "kind": "human"},
    "Meena (authorized approver)": {"id": "u-apr-1", "role": "authorized_approver", "kind": "human"},
    "AI assistant (claims approver role)": {"id": "ai-assist", "role": "authorized_approver", "kind": "ai"},
    "Batch service account": {"id": "svc-batch", "role": "authorized_approver", "kind": "service"},
    "Screening system": {"id": "svc-screening", "role": "screening_system", "kind": "service"},
}
ACTIONS = ["start_check", "request_evidence", "evidence_received", "evidence_complete", "screening_alert",
           "clear_hold", "submit_for_decision", "approve", "reject"]

st.set_page_config(page_title="KYC decision gate POC", layout="wide")
if "svc" not in st.session_state:
    st.session_state.svc = CaseService()
    st.session_state.svc.create_case("CASE-1001", "key-1001", ACTORS["Priya (KYC analyst)"])
svc = st.session_state.svc

st.title("KYC case workbench: human decision gate")
st.caption("Synthetic case. Rules come from feature.yaml (version %s). Every attempt is audited." % svc.version)
svc.ai_assist_enabled = st.toggle("AI assistance enabled", value=svc.ai_assist_enabled)
case = svc.cases["CASE-1001"]
c1, c2, c3 = st.columns(3)
c1.metric("Case", case["case_id"])
c2.metric("State", case["state"])
c3.metric("Screening hold", "OPEN" if case["hold_open"] else "none")
suggestion = svc.ai_suggest("CASE-1001")
st.info(suggestion if suggestion else "AI assistance is off. The case continues with people only.")

with st.form("act"):
    actor = st.selectbox("Who is acting", list(ACTORS))
    action = st.selectbox("Action", ACTIONS)
    reason = st.text_input("Reason")
    evidence = st.text_input("Evidence references (comma separated)", "DOC-PAN-001, SCR-REF-77")
    if st.form_submit_button("Submit"):
        refs = [e.strip() for e in evidence.split(",") if e.strip()]
        r = svc.act("CASE-1001", action, ACTORS[actor], reason or None, refs)
        (st.success if r["ok"] else st.error)(f"{'Accepted' if r['ok'] else 'Refused'} · {r['rule_id']} · {r['message']}")

st.subheader("Audit trail")
st.dataframe(svc.audit[::-1], use_container_width=True)

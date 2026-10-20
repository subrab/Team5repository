"""
AI Friday iteration engine (lab edition).

Implements the AI Friday Quick Guide quality loop on the lab's LiteLLM gateway models:
  1 Freeze   - the WRITER model produces the deliverable from its Markdown instruction file
  2 Review   - an independent EXAMINER model (different family) reviews, not rewrites
  3 Score    - six weighted scorecard dimensions; this tool recalculates the weighted total
     & trace - a gap register with Gap IDs, severity, evidence and status, kept across rounds
  4 Fix      - the WRITER remediates Critical and High gaps first and logs Gap ID -> change -> where
     & recheck  until the score reaches the target with no open Critical or High gaps.
The owner adds real-world notes each round and may consciously accept non-critical gaps.
A cross-pack review checks all deliverables together.

Team sync goes through the team's Gogs repository: pull before each round, commit and push after it.

Commands (from the repository folder, in the VS Code terminal):
  python iterate.py check            setup check for this laptop (run first)
  python iterate.py models           list the models the team key can use
  python iterate.py clarify | spec | dsl | testcases   SPEC-driven agent chain for the POC (human gate between stages)
  python iterate.py trace            POC traceability matrix: Requirement -> Spec -> Rule -> Code -> Test
  python iterate.py codereview       independent AI code quality score and report for the POC
  python iterate.py score D1 file.md calibration: score any document (e.g. a reference D1) with our reviewer
  python iterate.py variance D2      run an instruction on two models and compare structure (playbook step 5)
  python iterate.py pack             assemble DECISION-PACK.md (the five deliverables, for submission)
  python iterate.py D1               run D1 until done (pauses after each round for your notes)
  python iterate.py D1 --rounds 3    at most 3 rounds this time
  python iterate.py D1 --auto        no pause between rounds
  python iterate.py crosscheck       cross-pack consistency review of all deliverables (Deepak)
  python iterate.py status           whole-team progress
  python iterate.py report           iteration-report.html + ITERATIONS.md

Owner notes (notes/D1.md etc.): write corrections in plain words. To consciously accept a
non-critical gap, add a line:  ACCEPT G-03: reason
Settings: config.json (shared) + local.json (your name and key path; never committed).
Only the Python standard library is used.
"""
import argparse, csv, datetime, json, re, ssl, subprocess, sys, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
if (ROOT / "local.json").exists():
    CFG.update(json.loads((ROOT / "local.json").read_text(encoding="utf-8")))
MEMBER = CFG.get("member", "").strip()
LOG_DIR, GAP_DIR = ROOT / "logs", ROOT / "gaps"
LOG_CSV = LOG_DIR / f"{MEMBER or 'me'}.csv"
WEIGHTS = CFG["scorecard"]
FIELDS = ["time", "deliverable", "version", "owner", "writer_model", "examiner_model", "score", "criteria",
          "critical_open", "high_open", "gaps_closed", "gaps_accepted", "top_fixes", "owner_notes_used",
          "instruction_version", "tokens", "est_cost_usd"]
SEP = "===CHANGE LOG==="


# ---------------------------------------------------------------- model gateway
def api_key():
    if CFG.get("api_key"):
        return CFG["api_key"].strip()
    p = Path(CFG.get("api_key_file", ""))
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    sys.exit("No API key found. Set api_key_file in local.json to your team's key.txt path.")


def ssl_ctx():
    if CFG.get("ssl_verify", False):
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # lab gateway uses an internal certificate (same as verify=False in testing.py)
    return ctx


def http(method, path, body=None):
    url = CFG["base_url"].rstrip("/") + path
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {api_key()}", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300, context=ssl_ctx()) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"\nThe gateway refused the call ({e.code}):\n{e.read().decode(errors='replace')[:600]}\n"
                 "Check the model name (python iterate.py models) and the key path in local.json.")
    except urllib.error.URLError as e:
        sys.exit(f"\nCould not reach {url}: {e.reason}. Check base_url in config.json and the network.")


def call_model(model, system, user, max_tokens):
    """Returns (text, total_tokens)."""
    if CFG["provider"] == "mock":
        return mock_reply(system, user), 0
    data = http("POST", "/chat/completions", {"model": model, "max_tokens": max_tokens, "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": user}]})
    return data["choices"][0]["message"]["content"] or "", data.get("usage", {}).get("total_tokens", 0)


def mock_reply(system, user):
    """Free rehearsal mode: fake but well-formed answers so the team can practise the loop."""
    if "Instruction: Requirement Clarifier" in system:
        return ("## Business Objective\nMock objective\n## Requirements\n| REQ-ID | User story | Acceptance criteria |\n| --- | --- | --- |\n"
                "| REQ-001 | As a user, I want X, so that Y | AC-001: Given A, when B, then C |\n"
                "| REQ-002 | As a user, I want Z, so that W | AC-002: Given D, when E, then F |\n## Assumptions\nNone identified\n")
    if "Instruction: Spec Generator" in system:
        return ("# Feature: Mock\n## Specification\n| SPEC-ID | Implements | Specification |\n| --- | --- | --- |\n"
                "| SPEC-001 | REQ-001 | Mock |\n| SPEC-002 | REQ-002 | Mock |\n## Traceability\n- REQ-001 → SPEC-001 → CODE-001 → TEST-001\n- REQ-002 → SPEC-002 → CODE-002 → TEST-002\n")
    if "Instruction: DSL Converter" in system:
        bad = "FAILED VALIDATION" not in user  # first attempt deliberately incomplete, to exercise the retry
        y = ('feature:\n  id: FEATURE-001\n  name: "Mock"\n  objective: "Mock"\n  version: "1.0"\nactors: [user]\nworkflow:\n  - step_id: WF-001\n    description: "x"\n'
             'rules:\n  - rule_id: RULE-001\n    implements: SPEC-001\n    when: a\n    then: b\n  - rule_id: RULE-002\n    implements: SPEC-002\n    when: c\n    then: d\n'
             'validations: []\nexceptions: []\ndata_model: []\noutput_contract:\n  fields: [x]\nnfr: []\ntraceability:\n'
             '  - requirement: REQ-001\n    spec: SPEC-001\n    code: CODE-001\n    test: TEST-001\n')
        return y if bad else y + '  - requirement: REQ-002\n    spec: SPEC-002\n    code: CODE-002\n    test: TEST-002\n'
    if "Instruction: Test Case Generator" in system:
        return "## Test Cases\n| TEST-ID | Type | REQ | AC |\n| --- | --- | --- | --- |\n| TEST-001 | Positive | REQ-001 | AC-001 |\n| TEST-002 | Negative | REQ-002 | AC-002 |\n"
    if "Instruction: Code review" in system:
        return json.dumps({"readiness_status": "Ready with conditions", "scores": {"Requirement completeness": 92, "Traceability": 95, "Security": 88,
            "Maintainability & standards": 85, "Test coverage": 80, "Production readiness": 78},
            "gaps": [{"id": "C-01", "location": "src/router.py: route()", "finding": "Mock: no test for missing risk_score",
                      "severity": "Medium", "evidence": "item.get('risk_score', 1)", "action": "Add an edge-case test"}],
            "top_fixes": ["Add edge-case tests"]})
    if "Instruction: Cross-pack" in system:
        return json.dumps({"readiness_score": 84, "gaps": [{"id": "X-01", "deliverables": ["D1", "D5"],
                "finding": "Mock: names differ between D1 and D5", "severity": "High", "evidence": "mock",
                "fix": "D5: use the D1 stakeholder names"}]})
    if "Instruction: EXAMINER" in system:
        v = len(re.findall(r"^## Section", user.split("DELIVERABLE:")[-1], re.M))
        s = min(55 + 10 * v, 97)
        open_high = v < 4
        return json.dumps({"scores": {k: s for k in WEIGHTS}, "justifications": {"Coverage": "mock"},
            "gaps": [{"id": "G-01", "location": "Pain Points", "finding": "Mock: no figures from the case",
                      "severity": "High", "evidence": "row 1", "action": "Add the case's figures",
                      "status": "Open" if open_high else "Closed"},
                     {"id": "G-02", "location": "Assumptions", "finding": "Mock: assumption without owner",
                      "severity": "Medium", "evidence": "A2", "action": "Name an owner",
                      "status": "Accepted" if "ACCEPT G-02" in user else "Open"}],
            "top_fixes": ["Add the case's figures to each pain point", "Name an owner for every assumption",
                          "Map each constraint to a design implication"]})
    if user.startswith("VARIANCE TEST"):
        fmt = system.split("## 7. Output Format", 1)[-1].split("## 8.", 1)[0]
        return "\n\n".join(re.findall(r"(?m)^###\s+.+$", fmt)) + "\n\nMock content."
    current = user.split("CURRENT VERSION:")[-1] if "CURRENT VERSION:" in user else ""
    n = len(re.findall(r"^## Section", current, re.M)) + 1
    doc = "# Draft (mock)\n\n" + "\n\n".join(f"## Section {i}\nMock content." for i in range(1, n + 1))
    return doc + (f"\n{SEP}\nG-01 -> added case figures -> Pain Points" if current else "")


# ---------------------------------------------------------------- git (Gogs) sync
def git(*args):
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return False, "git not found"


def has_remote():
    return git("remote")[1].strip() != ""


def pull():
    if (ROOT / ".git").exists() and has_remote():
        ok, out = git("pull", "--rebase", "--autostash", "-q")
        if not ok:
            git("rebase", "--abort")
            print(f"  (could not pull teammates' updates: {out[:200]}. Carrying on locally; tell the team lead.)")


def commit_and_push(msg, tag=None):
    if not (ROOT / ".git").exists():
        if not git("init", "-q")[0]:
            print("  (git not found: versions are still saved in docs/versions, gaps/ and logs/)")
            return
    git("config", "user.name", MEMBER or "AI Friday team")
    git("config", "user.email", f"{(MEMBER or 'team').lower()}@ai-lab.local")
    git("add", "-A")
    git("commit", "-q", "-m", msg)
    if tag:
        git("tag", "-a", tag, "-m", msg)  # annotated, so --follow-tags shares it with the team
    if has_remote():
        pull()
        ok, out = git("push", "-q", "--follow-tags")
        print("  pushed to the team repository" if ok else f"  (push failed: {out[:200]}. Work is saved here; tell the team lead.)")


# ---------------------------------------------------------------- helpers
def read(p, default=""):
    p = ROOT / p
    return p.read_text(encoding="utf-8") if p.exists() else default


def parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None


def instruction(name):
    text = read(f"instructions/{name}.md")
    if not text:
        sys.exit(f"Missing instructions/{name}.md")
    m = re.search(r"\*\*Version:\*\*\s*([\w.]+)", text)
    return text, (m.group(1) if m else "?")


def weighted(scores):
    """Recalculate the weighted total ourselves; never trust the model's arithmetic."""
    total = sum(WEIGHTS.values())
    return round(sum(float(scores.get(k, 0)) * w for k, w in WEIGHTS.items()) / total, 1)


def team_history(d=None):
    rows = []
    for f in sorted(LOG_DIR.glob("*.csv")) if LOG_DIR.exists() else []:
        with f.open(encoding="utf-8") as fh:
            rows += list(csv.DictReader(fh))
    rows.sort(key=lambda r: (r["time"], r["deliverable"], int(r["version"])))
    return [r for r in rows if d is None or r["deliverable"] == d]


def log_round(row):
    LOG_DIR.mkdir(exist_ok=True)
    new = not LOG_CSV.exists()
    with LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})


def upstream_text(d):
    parts = []
    for u in CFG["deliverables"][d].get("uses", []):
        p = ROOT / "docs" / f"{u}.md"
        if p.exists():
            parts.append(f"--- {u}: {CFG['deliverables'][u]['title']} (latest team version) ---\n"
                         + p.read_text(encoding="utf-8")[:12000])
    return "\n\n".join(parts)


def team_corrections():
    """Every owner's notes and every consciously accepted gap: the evidence of human judgement."""
    parts = []
    for d in CFG["deliverables"]:
        n = read(f"notes/{d}.md").strip()
        if n:
            parts.append(f"--- {d} owner notes ({CFG['deliverables'][d]['owner']}) ---\n{n}")
        acc = [g for g in load_gaps(d) if g.get("status") == "Accepted"]
        if acc:
            parts.append(f"--- {d} gaps consciously accepted ---\n" + "\n".join(f"{g['id']}: {g.get('finding', '')}" for g in acc))
    for f in sorted(GAP_DIR.glob("*_changes.md")) if GAP_DIR.exists() else []:
        parts.append(f"--- {f.stem} (AI remediation log, summary) ---\n" + f.read_text(encoding="utf-8")[:1500])
    return "\n\n".join(parts) or "No notes or accepted gaps recorded yet."


def sync_case():
    s = CFG.get("shared_case_file", "").strip()
    if s and Path(s).is_file():
        src, dst = Path(s), ROOT / "case" / "case.md"
        if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def load_gaps(name):
    p = GAP_DIR / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def accepted_from_notes(notes):
    return {m.group(1).upper(): m.group(2).strip() for m in re.finditer(r"ACCEPT\s+(G-\d+)\s*:\s*(.+)", notes, re.I)}


def save_register(d, version, gaps, scores, total, accepted, changes):
    GAP_DIR.mkdir(exist_ok=True)
    (GAP_DIR / f"{d}.json").write_text(json.dumps(gaps, indent=2), encoding="utf-8")
    sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    rows = sorted(gaps, key=lambda g: (g.get("status") != "Open", sev_order.get(g.get("severity"), 4), g.get("id", "")))
    cell = lambda s: str(s).replace("|", "/").replace("\n", " ")
    md = [f"# {d} gap register", "", f"Round v{version} · weighted score **{total}** · independent reviewer: {CFG['examiner_model']}", "",
          "## Scorecard", "", "| Dimension | Weight | Score |", "| --- | --- | --- |"]
    md += [f"| {k} | {w}% | {scores.get(k, '')} |" for k, w in WEIGHTS.items()]
    md += [f"| **Weighted total** | 100% | **{total}** |", "", "## Gaps", "",
           "| Gap ID | Location | Finding | Severity | Evidence | Action | Status |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for g in rows:
        st = g.get("status", "Open") + (f" (owner: {accepted[g['id']]})" if g.get("id") in accepted else "")
        md.append("| " + " | ".join(cell(g.get(k, "")) for k in ("id", "location", "finding", "severity", "evidence", "action")) + f" | {cell(st)} |")
    (GAP_DIR / f"{d}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if changes:
        with (GAP_DIR / f"{d}_changes.md").open("a", encoding="utf-8") as f:
            f.write(f"\n## v{version} remediation (Gap ID -> change -> where)\n\n{changes.strip()}\n")


def cross_gaps_for(d):
    return [g for g in load_gaps("CROSS-PACK") if d in g.get("deliverables", [])]


# ---------------------------------------------------------------- the loop
def run(d, rounds, auto):
    spec = CFG["deliverables"].get(d)
    if not spec:
        sys.exit(f"Unknown deliverable {d}. Choose from: {', '.join(CFG['deliverables'])}")
    if MEMBER and spec["owner"] != MEMBER:
        sys.exit(f"{d} belongs to {spec['owner']}. Only the owner runs it, so nobody overwrites anyone.")
    target = CFG["target_score"]
    doc_path = ROOT / "docs" / f"{d}.md"
    vdir = ROOT / "docs" / "versions"; vdir.mkdir(parents=True, exist_ok=True)

    for _ in range(rounds):
        pull(); sync_case()
        w_instr, w_ver = instruction(d)
        e_instr, e_ver = instruction("examiner")
        rubric = read("rubrics/jury_rubric.md") + "\n\n" + read(f"rubrics/{d}.md")
        hist = team_history(d)
        version = int(hist[-1]["version"]) if hist else 0
        last_score = float(hist[-1]["score"]) if hist else None
        gaps = load_gaps(d)
        case, notes, up = read("case/case.md"), read(f"notes/{d}.md").strip(), upstream_text(d)
        accepted = {k: v for k, v in accepted_from_notes(notes).items()
                    if any(g["id"] == k and g.get("severity") != "Critical" for g in gaps)}
        blocking = [g for g in gaps if g.get("status") == "Open" and g.get("severity") in ("Critical", "High")]
        if hist and last_score >= target and not blocking:
            print(f"{d} is done: {last_score} with no open Critical or High gaps.")
            return
        team_ctx = f"\n\nTEAM DOCUMENTS TO STAY CONSISTENT WITH:\n{up}" if up else ""
        if spec.get("include_trace") and (ROOT / "TRACEABILITY.md").exists():
            team_ctx += f"\n\nPOC TRACEABILITY MATRIX (generated from the repository; real evidence):\n{read('TRACEABILITY.md')}"
        if spec.get("include_trace") and (GAP_DIR / "CODE-REVIEW.md").exists():
            team_ctx += f"\n\nPOC CODE QUALITY REPORT (independent AI review; real evidence):\n{read('gaps/CODE-REVIEW.md')}"
        if spec.get("include_team_notes"):
            team_ctx += f"\n\nTEAM HUMAN-CORRECTIONS LOG (the only source for AI-use reflection):\n{team_corrections()}"
        if notes:
            team_ctx += f"\n\nOWNER'S NOTES (real-world facts and, for the POC, the only source of results):\n{notes}"
        cross = cross_gaps_for(d)
        current = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
        if not current:
            prompt = f"CASE:\n{case}{team_ctx}\n\nWHAT THE REVIEWER WILL CHECK:\n{rubric}\n\nWrite version 1 of the deliverable."
        else:
            open_gaps = [g for g in gaps if g.get("status") == "Open" and g.get("id") not in accepted]
            prompt = (f"CASE:\n{case}{team_ctx}\n\nWHAT THE REVIEWER WILL CHECK:\n{rubric}\n\nCURRENT VERSION:\n{current}\n\n"
                      f"GAP REGISTER (open gaps to remediate, Critical and High first):\n{json.dumps(open_gaps, indent=1)}" +
                      (f"\n\nCROSS-PACK GAPS INVOLVING {d}:\n{json.dumps(cross, indent=1)}" if cross else "") +
                      f"\n\nReturn the complete remediated document, then {SEP} and the change log.")
        version += 1
        print(f"\n[{d} v{version}] writing with {CFG['writer_model']} (instruction v{w_ver}) ...")
        out, t1 = call_model(CFG["writer_model"], w_instr + "\n\nFollow this instruction file exactly.", prompt, CFG["writer_max_tokens"])
        draft, _, changes = out.partition(SEP)
        draft = draft.strip() + "\n"
        doc_path.write_text(draft, encoding="utf-8")
        (vdir / f"{d}_v{version}.md").write_text(draft, encoding="utf-8")

        print(f"[{d} v{version}] independent review with {CFG['examiner_model']} ...")
        raw, t2 = call_model(CFG["examiner_model"], e_instr,
            f"CASE:\n{case}\n\nRUBRIC:\n{rubric}\n\nDELIVERABLE INSTRUCTION:\n{w_instr}{team_ctx}\n\n"
            f"PREVIOUS GAP REGISTER:\n{json.dumps(gaps, indent=1)}\n\n"
            f"OWNER-ACCEPTED GAPS:\n{json.dumps(accepted, indent=1) if accepted else 'none'}"
            f"{' ' + ' '.join('ACCEPT ' + k for k in accepted) if accepted else ''}\n\nDELIVERABLE:\n{draft}",
            CFG["examiner_max_tokens"])
        res = parse_json(raw)
        if not res or "scores" not in res:
            print("  The reviewer's reply was not in the agreed format; this round is not scored. Run again.")
            continue
        scores, new_gaps = res["scores"], res.get("gaps", [])
        for g in new_gaps:  # enforce rules in code, not just in the prompt
            if g.get("id") in accepted and g.get("severity") != "Critical" and g.get("status") == "Open":
                g["status"] = "Accepted"
        total = weighted(scores)
        crit = sum(1 for g in new_gaps if g.get("status") == "Open" and g.get("severity") == "Critical")
        high = sum(1 for g in new_gaps if g.get("status") == "Open" and g.get("severity") == "High")
        closed = sum(1 for g in new_gaps if g.get("status") == "Closed")
        acc = sum(1 for g in new_gaps if g.get("status") == "Accepted")
        save_register(d, version, new_gaps, scores, total, accepted, changes)
        tok = t1 + t2
        cost = round(tok / 1e6 * CFG.get("blended_usd_per_million_tokens", 0), 4)
        fixes = res.get("top_fixes", [])
        log_round({"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "deliverable": d, "version": version,
                   "owner": spec["owner"], "writer_model": CFG["writer_model"], "examiner_model": CFG["examiner_model"],
                   "score": total, "criteria": json.dumps(scores), "critical_open": crit, "high_open": high,
                   "gaps_closed": closed, "gaps_accepted": acc, "top_fixes": json.dumps(fixes),
                   "owner_notes_used": "yes" if notes else "no", "instruction_version": f"{w_ver}/{e_ver}",
                   "tokens": tok, "est_cost_usd": cost})
        done = total >= target and crit == 0 and high == 0
        delta = f"{last_score} -> {total}" if last_score is not None else f"{total}"
        commit_and_push(f"{d} v{version}: score {delta} | gaps open C{crit}/H{high}, closed {closed}, accepted {acc} | "
                        f"owner {spec['owner']} | instruction v{w_ver}{' | owner notes applied' if notes else ''}",
                        tag=f"{d.lower()}-v{version}-done" if done else None)

        print(f"[{d} v{version}] SCORE {total}/100   open gaps: {crit} Critical, {high} High   closed: {closed}   (tokens {tok}, ~${cost})")
        for k, w in WEIGHTS.items():
            print(f"   {k:30} {w:>3}%  {scores.get(k, '-')}")
        print(f"   Gap register: gaps/{d}.md")
        if done:
            print(f"\nDone: {total} with no open Critical or High gaps. Tagged. Tell Deepak.")
            return
        if not auto:
            print(f"\nOWNER STEP: read docs/{d}.md and gaps/{d}.md (Ctrl+Shift+V). Write corrections in notes/{d}.md."
                  f"\nTo consciously accept a non-critical gap, add:  ACCEPT G-03: your reason")
            if input("Press Enter for the next round, or type q to stop: ").strip().lower() == "q":
                return


def crosscheck():
    pull(); sync_case()
    instr, ver = instruction("cross_pack")
    docs = {d: (ROOT / "docs" / f"{d}.md") for d in CFG["deliverables"]}
    pack = "\n\n".join(f"=== {d}: {CFG['deliverables'][d]['title']} ===\n" +
                       (p.read_text(encoding="utf-8")[:12000] if p.exists() else "(not written yet)") for d, p in docs.items())
    print(f"Cross-pack review with {CFG['examiner_model']} ...")
    raw, tok = call_model(CFG["examiner_model"], instr, f"CASE:\n{read('case/case.md')}\n\nALL DELIVERABLES:\n{pack}",
                          CFG["examiner_max_tokens"])
    res = parse_json(raw)
    if not res or "gaps" not in res:
        sys.exit("The reviewer's reply was not in the agreed format. Run again.")
    gaps, score = res["gaps"], float(res.get("readiness_score", 0))
    GAP_DIR.mkdir(exist_ok=True)
    (GAP_DIR / "CROSS-PACK.json").write_text(json.dumps(gaps, indent=2), encoding="utf-8")
    cell = lambda s: str(s).replace("|", "/").replace("\n", " ")
    md = ["# Cross-pack consistency review", "", f"Readiness score **{score}** · reviewer {CFG['examiner_model']} · "
          f"{datetime.datetime.now():%Y-%m-%d %H:%M}", "", "| Gap ID | Deliverables | Finding | Severity | Evidence | Fix |",
          "| --- | --- | --- | --- | --- | --- |"]
    md += [f"| {g.get('id')} | {', '.join(g.get('deliverables', []))} | {cell(g.get('finding'))} | {g.get('severity')} | "
           f"{cell(g.get('evidence'))} | {cell(g.get('fix'))} |" for g in gaps]
    (GAP_DIR / "CROSS-PACK.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    prev = team_history("PACK")
    v = int(prev[-1]["version"]) + 1 if prev else 1
    crit = sum(1 for g in gaps if g.get("severity") == "Critical")
    high = sum(1 for g in gaps if g.get("severity") == "High")
    log_round({"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "deliverable": "PACK", "version": v,
               "owner": MEMBER or "Deepak", "writer_model": "-", "examiner_model": CFG["examiner_model"], "score": score,
               "critical_open": crit, "high_open": high, "top_fixes": json.dumps([g.get("fix", "") for g in gaps[:3]]),
               "instruction_version": ver, "tokens": tok,
               "est_cost_usd": round(tok / 1e6 * CFG.get("blended_usd_per_million_tokens", 0), 4)})
    commit_and_push(f"Cross-pack review v{v}: readiness {score} | {crit} Critical, {high} High across deliverables")
    print(f"Readiness {score}. {len(gaps)} cross-pack gaps ({crit} Critical, {high} High). See gaps/CROSS-PACK.md.")
    owners = sorted({CFG['deliverables'][d]['owner'] for g in gaps for d in g.get('deliverables', []) if d in CFG['deliverables']})
    if owners:
        print("These owners will see the gaps automatically in their next round: " + ", ".join(owners))


# ---------------------------------------------------------------- team views
def status():
    pull()
    allh = team_history()
    for d, spec in list(CFG["deliverables"].items()) + [("PACK", {"title": "Cross-pack review", "owner": "Deepak"}), ("CODE", {"title": "POC code review", "owner": "Deepak"}),
                                                    ("REQ", {"title": "Agent: requirements", "owner": "Murali"}), ("SPEC", {"title": "Agent: specification", "owner": "Subramaniabharathi"}),
                                                    ("DSL", {"title": "Agent: YAML DSL", "owner": "Muthuvel"}), ("TESTS", {"title": "Agent: test cases", "owner": "Deepak"})]:
        h = [r for r in allh if r["deliverable"] == d]
        last = (f"v{h[-1]['version']}  score {h[-1]['score']}  open C{h[-1].get('critical_open', '?')}/H{h[-1].get('high_open', '?')}"
                if h else "not started")
        print(f"{d:5} {spec['title'][:38]:38} {spec['owner']:18} {last}")
    print(f"\nTotal rounds: {len(allh)}   tokens: {sum(int(r['tokens'] or 0) for r in allh)}   "
          f"est. cost: ${sum(float(r['est_cost_usd'] or 0) for r in allh):.2f}")


def report():
    pull()
    rows = team_history()
    tpl = (ROOT / "report_template.html").read_text(encoding="utf-8")
    (ROOT / "iteration-report.html").write_text(
        tpl.replace("/*DATA*/[]", json.dumps(rows)).replace("/*TARGET*/95", str(CFG["target_score"])), encoding="utf-8")
    md = ["# Iteration log", "", f"{len(rows)} rounds, generated {datetime.datetime.now():%Y-%m-%d %H:%M}. "
          "Gap registers are in gaps/, remediation change logs in gaps/*_changes.md.", "",
          "| Time | Deliverable | Ver | Owner | Instruction | Reviewer | Score | Open C/H | Closed | Accepted | Owner notes |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        md.append(f"| {r['time']} | {r['deliverable']} | v{r['version']} | {r['owner']} | {r.get('instruction_version', '')} | "
                  f"{r['examiner_model']} | {r['score']} | {r.get('critical_open', '')}/{r.get('high_open', '')} | "
                  f"{r.get('gaps_closed', '')} | {r.get('gaps_accepted', '')} | {r.get('owner_notes_used', '')} |")
    (ROOT / "ITERATIONS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote iteration-report.html (double-click to open) and ITERATIONS.md: {len(rows)} rounds.")


def run_poc_tests(test_dir):
    """Run every test_* function in poc/tests with a tiny built-in runner (no pytest needed)."""
    import importlib.util, traceback
    results = {}
    for f in sorted(test_dir.glob("test_*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:
            results[f"{f.name}::(import)"] = (f"error: {e}", "")
            continue
        for name in sorted(n for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n))):
            fn = getattr(mod, name)
            doc = fn.__doc__ or ""
            try:
                fn()
                results[f"{f.name}::{name}"] = ("pass", doc)
            except AssertionError:
                results[f"{f.name}::{name}"] = ("FAIL", doc)
            except Exception as e:
                results[f"{f.name}::{name}"] = (f"error: {type(e).__name__}", doc)
    return results


# ---------------------------------------------------------------- YAML DSL reader (PyYAML if present, else a small subset reader)
def load_yaml(text):
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        pass
    def scalar(v):
        v = v.strip()
        if v == "":
            return None
        if v[0] in "\"'" and v[-1] == v[0]:
            return v[1:-1]
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            return [scalar(x) for x in inner.split(",")] if inner else []
        if v in ("true", "false"):
            return v == "true"
        for cast in (int, float):
            try:
                return cast(v)
            except ValueError:
                pass
        return v
    L = []
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        if '"' not in raw and "'" not in raw:
            raw = re.sub(r"\s+#.*$", "", raw)
        L.append([len(raw) - len(raw.lstrip()), raw.strip()])
    def block(i, ind):
        if L[i][1].startswith("- "):
            out = []
            while i < len(L) and L[i][0] == ind and L[i][1].startswith("- "):
                c = L[i][1][2:]
                if re.match(r"^[\w\-]+:(\s|$)", c):
                    L[i] = [ind + 2, c]
                    item, i = mapping(i, ind + 2)
                    out.append(item)
                else:
                    out.append(scalar(c)); i += 1
            return out, i
        return mapping(i, ind)
    def mapping(i, ind):
        out = {}
        while i < len(L) and L[i][0] == ind and not L[i][1].startswith("- "):
            k, _, v = L[i][1].partition(":")
            i += 1
            if v.strip():
                out[k.strip()] = scalar(v)
            elif i < len(L) and (L[i][0] > ind or (L[i][0] == ind and L[i][1].startswith("- "))):
                out[k.strip()], i = block(i, L[i][0])
            else:
                out[k.strip()] = None
        return out, i
    return block(0, L[0][0])[0] if L else {}


DSL_KEYS = ["feature", "actors", "workflow", "rules", "validations", "exceptions", "data_model", "output_contract", "nfr", "traceability"]


def validate_dsl(text, spec_text=""):
    """Schema validation before handoff. Returns a list of problems (empty = valid)."""
    try:
        d = load_yaml(text)
    except Exception as e:
        return [f"YAML does not parse: {e}"]
    if not isinstance(d, dict):
        return ["YAML top level must be a mapping"]
    probs = [f"missing top-level key: {k}" for k in DSL_KEYS if k not in d]
    for r in d.get("rules") or []:
        for k in ("rule_id", "implements", "when", "then"):
            if not isinstance(r, dict) or k not in r:
                probs.append(f"rule {r.get('rule_id', '?') if isinstance(r, dict) else r} missing '{k}'")
    for t in d.get("traceability") or []:
        if not isinstance(t, dict) or not all(k in t for k in ("requirement", "spec", "code", "test")):
            probs.append(f"traceability entry incomplete: {t}")
    if spec_text:
        mapped = {t.get("spec") for t in d.get("traceability") or [] if isinstance(t, dict)}
        for sid in sorted(set(re.findall(r"SPEC-\d+", spec_text))):
            if sid not in mapped:
                probs.append(f"{sid} from the spec is missing from the traceability mapping")
    return probs


# ---------------------------------------------------------------- SPEC-driven agent chain (Best Practices section 6)
AGENTS = {
    "clarify":   {"instr": "requirement_clarifier", "out": "poc/requirements.md", "needs": [], "label": "REQ",
                  "role": "Analyst", "check": r"REQ-\d+"},
    "spec":      {"instr": "spec_generator", "out": "poc/spec.md", "needs": ["poc/requirements.md"], "label": "SPEC",
                  "role": "Architect", "check": r"SPEC-\d+"},
    "dsl":       {"instr": "dsl_converter", "out": "poc/feature.yaml", "needs": ["poc/spec.md"], "label": "DSL",
                  "role": "Developer", "check": None},
    "testcases": {"instr": "test_designer", "out": "poc/test_cases.md",
                  "needs": ["poc/requirements.md", "poc/spec.md", "poc/feature.yaml"], "label": "TESTS",
                  "role": "Tester", "check": r"TEST-\d+"},
}
GATE = re.compile(r"^\s*(?:#|<!--)?\s*Approved-by:\s*(?![<\'])\w", re.I | re.M)  # a real name at line start; the stamp's placeholder does not count


def agent(stage):
    a = AGENTS[stage]
    owner = CFG.get("poc_agents", {}).get(stage)
    if MEMBER and owner and owner != MEMBER:
        sys.exit(f"The {stage} agent belongs to {owner} ({a['role']}).")
    pull(); sync_case()
    for need in a["needs"]:  # human review gate
        if not GATE.search(read(need)):
            sys.exit(f"Human review gate: {need} has not been approved yet. Its owner reviews it, edits anything wrong, "
                     f"and adds a first line 'Approved-by: <name>'. Then run this agent again.")
    instr, ver = instruction(a["instr"])
    inputs = [f"CASE:\n{read('case/case.md')}"]
    for d in ("D1", "D2", "D3"):
        if (ROOT / "docs" / f"{d}.md").exists():
            inputs.append(f"TEAM DOCUMENT {d}:\n{read(f'docs/{d}.md')[:8000]}")
    if stage == "clarify":
        q = read("notes/POC.md").strip()
        if not q:
            sys.exit("Write the POC question in notes/POC.md first (what part of our solution most needs evidence?).")
        inputs.append(f"POC QUESTION:\n{q}")
    for need in a["needs"]:
        inputs.append(f"APPROVED INPUT {need}:\n{read(need)}")
    feedback, problems, out, tok = "", [], "", 0
    for attempt in (1, 2):
        print(f"{stage} agent ({a['role']}) with {CFG['writer_model']}, instruction v{ver}{' (retry after validation)' if attempt > 1 else ''} ...")
        out, t = call_model(CFG["writer_model"], instr + "\n\nFollow this instruction file exactly.",
                            "\n\n".join(inputs) + feedback, CFG["writer_max_tokens"])
        tok += t
        out = re.sub(r"^```\w*\n|\n```\s*$", "", out.strip()) + "\n"
        if stage == "dsl":
            problems = validate_dsl(out, read("poc/spec.md"))
        else:
            problems = [] if re.search(a["check"], out) else [f"no {a['label']} IDs found"]
            for rid in sorted(set(re.findall(r"REQ-\d+", " ".join(read(n) for n in a["needs"])))):
                if rid not in out:
                    problems.append(f"{rid} from the approved input was dropped")
        if not problems:
            break
        feedback = "\n\nYOUR PREVIOUS OUTPUT FAILED VALIDATION. Fix exactly these problems:\n- " + "\n- ".join(problems)
    path = ROOT / a["out"]
    stamp = (f"Generated by the {stage} agent (instruction v{ver}, {CFG['writer_model']}) on "
             f"{datetime.datetime.now():%Y-%m-%d %H:%M}. Review, edit, then add a first line 'Approved-by: <name>'.")
    if problems:
        rej = path.with_name(path.stem + ".rejected" + path.suffix)
        rej.write_text(out, encoding="utf-8")
        print("Validation failed twice; nothing handed on. Problems:\n- " + "\n- ".join(problems) + f"\nThe output is in {rej.relative_to(ROOT)}.")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((f"# {stamp}\n" if path.suffix == ".yaml" else f"<!-- {stamp} -->\n\n") + out, encoding="utf-8")
    prev = team_history(a["label"])
    v = int(prev[-1]["version"]) + 1 if prev else 1
    ids = sorted(set(re.findall(r"(?:REQ|SPEC|RULE|TEST)-\d+", out)))
    log_round({"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "deliverable": a["label"], "version": v,
               "owner": MEMBER or owner or "-", "writer_model": CFG["writer_model"], "examiner_model": "schema validation",
               "score": 0 if problems else 100, "critical_open": len(problems), "high_open": 0,
               "top_fixes": json.dumps(problems[:3]), "instruction_version": ver, "tokens": tok,
               "est_cost_usd": round(tok / 1e6 * CFG.get("blended_usd_per_million_tokens", 0), 4)})
    commit_and_push(f"{a['label']} agent v{v}: {'validated' if not problems else 'REJECTED by validation'} | "
                    f"{len(ids)} IDs | awaiting human gate ({a['role']})")
    if not problems:
        print(f"Wrote {a['out']}. Human gate: the {a['role']} reviews it, edits anything wrong, and adds 'Approved-by: <name>' on the first line.")


def trace():
    """Requirement -> Spec -> Rule (DSL) -> Code -> Test lineage for the POC, verified against the repository."""
    pull()
    poc = ROOT / "poc"
    if not (poc / "requirements.md").exists():
        sys.exit("No poc/requirements.md yet. Run the clarify agent first (see poc/README.md).")
    reqs = {}
    for line in read("poc/requirements.md").splitlines():
        m = re.match(r"\|\s*(REQ-\d+)\s*\|\s*([^|]*)\|", line)
        if m:
            reqs[m.group(1)] = m.group(2).strip()
    spec_text = read("poc/spec.md")
    dsl_text = read("poc/feature.yaml")
    dsl_problems = validate_dsl(dsl_text, spec_text) if dsl_text else ["poc/feature.yaml missing"]
    dsl = load_yaml(dsl_text) if dsl_text and not any("parse" in p for p in dsl_problems) else {}
    rules = {r.get("rule_id"): r.get("implements") for r in (dsl.get("rules") or []) if isinstance(r, dict)}
    links = {t.get("requirement"): t for t in (dsl.get("traceability") or []) if isinstance(t, dict)}
    code_text = {f.relative_to(poc).as_posix(): f.read_text(encoding="utf-8", errors="ignore")
                 for f in sorted((poc / "src").rglob("*")) if f.is_file() and f.suffix not in (".pyc",)} if (poc / "src").exists() else {}
    tests = run_poc_tests(poc / "tests") if (poc / "tests").exists() else {}
    rows, complete = [], 0
    for r, story in reqs.items():
        t = links.get(r, {})
        sid, cid, tid = t.get("spec"), t.get("code"), t.get("test")
        in_spec = bool(sid) and sid in spec_text
        rule_ids = [k for k, v in rules.items() if v == sid]
        code_files = [f for f, txt in code_text.items() if cid and cid in txt]
        num = r.split("-")[1].lstrip("0") or "0"
        mine = {k: v for k, v in tests.items() if re.search(rf"req[-_]?0*{num}(?!\d)", k, re.I) or (tid and tid in v[1])}
        named = [k for k, v in mine.items() if tid and tid in v[1]]
        gaps = [g for g, ok in (("not in DSL traceability", t), ("spec missing", in_spec), ("no rule", rule_ids),
                                ("code ID not found in src", code_files), ("no tests", mine),
                                (f"{tid} not found in tests", named or not tid)) if not ok]
        if any(v[0] != "pass" for v in mine.values()):
            gaps.append("failing test")
        complete += not gaps
        fmt = lambda xs: ", ".join(xs) or "-"
        rows.append(f"| {r} | {story[:80]} | {sid or '-'} | {fmt(rule_ids)} | {cid or '-'} ({fmt(code_files)}) | "
                    f"{fmt([k.split('::')[1] + ' ' + v[0] for k, v in mine.items()])} | {'Complete' if not gaps else 'Gap: ' + ', '.join(gaps)} |")
    passed = sum(v[0] == "pass" for v in tests.values())
    gates = {f: bool(GATE.search(read(f))) for f in ("poc/requirements.md", "poc/spec.md", "poc/feature.yaml", "poc/test_cases.md")}
    md = ["# Traceability matrix (POC)", "",
          f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M} by `python iterate.py trace`. Requirement -> Spec -> Rule (DSL) -> Code -> Test, checked against the repository.", "",
          f"**{complete} of {len(reqs)} requirements fully traced · tests {passed} of {len(tests)} passing · "
          f"DSL schema {'valid' if not dsl_problems else 'INVALID'}**", "",
          "| REQ | Story | Spec | Rule (DSL) | Code | Tests | Status |", "| --- | --- | --- | --- | --- | --- | --- |"] + rows
    md += ["", "**Human review gates:** " + " · ".join(f"{k.split('/')[-1]} {'approved' if v else 'NOT approved'}" for k, v in gates.items())]
    if dsl_problems:
        md += ["", "**DSL schema problems:** " + "; ".join(dsl_problems)]
    (ROOT / "TRACEABILITY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    commit_and_push(f"Traceability: {complete}/{len(reqs)} requirements fully traced, tests {passed}/{len(tests)} passing")
    print(f"{complete} of {len(reqs)} requirements fully traced; tests {passed}/{len(tests)} passing; "
          f"DSL {'valid' if not dsl_problems else 'invalid'}. See TRACEABILITY.md.")


def codereview():
    """Independent AI code quality score and report for the POC (Chennai Manifesto scene 11)."""
    pull()
    poc = ROOT / "poc"
    files = [f for d in ("src", "tests") for f in sorted((poc / d).rglob("*")) if (poc / d).exists()
             and f.is_file() and f.suffix in (".py", ".js", ".ts", ".java", ".cs", ".html", ".css", ".json", ".yaml", ".sql")]
    if not files:
        sys.exit("No POC code in poc/src or poc/tests yet.")
    code = "\n\n".join(f"=== {f.relative_to(poc).as_posix()} ===\n" + f.read_text(encoding="utf-8", errors="ignore")[:8000] for f in files)
    instr, ver = instruction("code_review")
    print(f"Code review with {CFG['examiner_model']} ...")
    raw, tok = call_model(CFG["examiner_model"], instr,
        f"REQUIREMENTS:\n{read('poc/requirements.md')}\n\nSPECIFICATION:\n{read('poc/spec.md')}\n\nRULES (DSL):\n{read('poc/feature.yaml')}"
        f"\n\nTEST CASES:\n{read('poc/test_cases.md')}"
        f"\n\nTRACEABILITY MATRIX:\n{read('TRACEABILITY.md', 'not generated yet')}\n\nCODE AND TESTS:\n{code}", CFG["examiner_max_tokens"])
    res = parse_json(raw)
    if not res or "scores" not in res:
        sys.exit("The reviewer's reply was not in the agreed format. Run again.")
    scores, gaps = res["scores"], res.get("gaps", [])
    total = round(sum(float(v) for v in scores.values()) / max(len(scores), 1), 1)
    crit = sum(1 for g in gaps if g.get("severity") == "Critical")
    high = sum(1 for g in gaps if g.get("severity") == "High")
    GAP_DIR.mkdir(exist_ok=True)
    cell = lambda s: str(s).replace("|", "/").replace("\n", " ")
    readiness = res.get("readiness_status", "not stated")
    md = ["# POC code quality report", "", f"Readiness: **{readiness}** · score **{total}** (average of six dimensions) · reviewer {CFG['examiner_model']} · "
          f"instruction v{ver} · {datetime.datetime.now():%Y-%m-%d %H:%M}", "", "| Dimension | Score |", "| --- | --- |"]
    md += [f"| {k} | {v} |" for k, v in scores.items()]
    md += ["", "| Gap ID | Location | Finding | Severity | Evidence | Action |", "| --- | --- | --- | --- | --- | --- |"]
    md += ["| " + " | ".join(cell(g.get(k, "")) for k in ("id", "location", "finding", "severity", "evidence", "action")) + " |" for g in gaps]
    (GAP_DIR / "CODE-REVIEW.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    prev = team_history("CODE")
    v = int(prev[-1]["version"]) + 1 if prev else 1
    log_round({"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "deliverable": "CODE", "version": v,
               "owner": MEMBER or "Deepak", "writer_model": "-", "examiner_model": CFG["examiner_model"], "score": total,
               "criteria": json.dumps(scores), "critical_open": crit, "high_open": high,
               "top_fixes": json.dumps(res.get("top_fixes", [])), "instruction_version": ver, "tokens": tok,
               "est_cost_usd": round(tok / 1e6 * CFG.get("blended_usd_per_million_tokens", 0), 4)})
    commit_and_push(f"Code review v{v}: POC code quality {total}, {readiness} | {crit} Critical, {high} High")
    print(f"POC code quality {total}, readiness: {readiness}. {len(gaps)} findings ({crit} Critical, {high} High). See gaps/CODE-REVIEW.md.")


def variance(d):
    """Playbook workflow step 5: run one instruction file on two different models and compare the structure."""
    spec = CFG["deliverables"].get(d)
    if not spec:
        sys.exit(f"Choose a deliverable: {', '.join(CFG['deliverables'])}")
    pull(); sync_case()
    instr, ver = instruction(d)
    fmt = instr.split("## 7. Output Format", 1)[-1].split("## 8.", 1)[0]
    expected = [re.sub(r"\s*\(.*$", "", h).strip() for h in re.findall(r"(?m)^###\s+(.+)$", fmt)]
    up = upstream_text(d)
    prompt = (f"VARIANCE TEST\n\nCASE:\n{read('case/case.md')}" + (f"\n\nTEAM DOCUMENTS:\n{up}" if up else "") +
              "\n\nWrite version 1 of the deliverable.")
    models = [CFG["writer_model"], CFG.get("variance_model", "azure_ai/genailab-maas-DeepSeek-V3-0324")]
    results, tok = [], 0
    for m in models:
        print(f"{d} instruction v{ver} on {m} ...")
        out, t = call_model(m, instr + "\n\nFollow this instruction file exactly.", prompt, CFG["writer_max_tokens"])
        tok += t
        found = [h for h in expected if re.search(rf"(?mi)^#+\s*{re.escape(h)}", out)]
        order_ok = [h for h in expected if h in found] == sorted(found, key=lambda h: out.lower().find(h.lower()))
        results.append({"model": m, "found": found, "missing": [h for h in expected if h not in found],
                        "order_ok": order_ok, "words": len(out.split())})
    conf = [round(100 * len(r["found"]) / max(len(expected), 1)) for r in results]
    ratio = round(min(r["words"] for r in results) / max(max(r["words"] for r in results), 1), 2)
    stable = min(conf) >= 90 and ratio >= 0.6
    vdir = ROOT / "instructions" / "variance"; vdir.mkdir(parents=True, exist_ok=True)
    md = [f"# Output variance test: {d} instruction v{ver}", "",
          f"{datetime.datetime.now():%Y-%m-%d %H:%M} · AI Friday Prompt Playbook, workflow step 5 and the Golden Rule "
          "(two different AI tools should produce a similar structure).", "",
          f"**Result: {'stable' if stable else 'NOT stable: refine the instruction'}**", "",
          "| Model | Required headings followed | Order kept | Words | Missing headings |", "| --- | --- | --- | --- | --- |"]
    md += [f"| {r['model']} | {c}% | {'yes' if r['order_ok'] else 'no'} | {r['words']} | {', '.join(r['missing']) or '-'} |" for r, c in zip(results, conf)]
    md += ["", f"Length ratio (shorter / longer): {ratio}. Stable means both models follow at least 90% of the required headings "
           "and their lengths are within the same range. If not stable, tighten the instruction (exact headings, an example, "
           "a length limit), raise its version, and test again."]
    (vdir / f"{d}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    prev = team_history(f"VAR-{d}")
    v = int(prev[-1]["version"]) + 1 if prev else 1
    log_round({"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "deliverable": f"VAR-{d}", "version": v,
               "owner": MEMBER or spec["owner"], "writer_model": " vs ".join(models), "examiner_model": "structure check",
               "score": min(conf), "instruction_version": ver, "tokens": tok,
               "est_cost_usd": round(tok / 1e6 * CFG.get("blended_usd_per_million_tokens", 0), 4)})
    commit_and_push(f"Variance test {d} instruction v{ver}: {conf[0]}% vs {conf[1]}% headings, length ratio {ratio} | "
                    f"{'stable' if stable else 'refine'}")
    print(f"{'Stable' if stable else 'Not stable'}: {conf[0]}% vs {conf[1]}% of required headings; length ratio {ratio}. "
          f"See instructions/variance/{d}.md")


def score_external(d, path):
    """Calibration: score any document (for example the organisers' reference D1) with our reviewer. Nothing is overwritten."""
    if d not in CFG["deliverables"]:
        sys.exit(f"Usage: python iterate.py score D1 path/to/document.md")
    f = Path(path)
    if not f.is_file():
        sys.exit(f"File not found: {path}")
    pull(); sync_case()
    w_instr, _ = instruction(d)
    e_instr, e_ver = instruction("examiner")
    rubric = read("rubrics/jury_rubric.md") + "\n\n" + read(f"rubrics/{d}.md")
    print(f"Calibration: scoring {f.name} as {d} with {CFG['examiner_model']} ...")
    raw, tok = call_model(CFG["examiner_model"], e_instr,
        f"CASE:\n{read('case/case.md')}\n\nRUBRIC:\n{rubric}\n\nDELIVERABLE INSTRUCTION:\n{w_instr}\n\n"
        f"PREVIOUS GAP REGISTER:\n[]\n\nOWNER-ACCEPTED GAPS:\nnone\n\nDELIVERABLE:\n{f.read_text(encoding='utf-8', errors='ignore')[:30000]}",
        CFG["examiner_max_tokens"])
    res = parse_json(raw)
    if not res or "scores" not in res:
        sys.exit("The reviewer's reply was not in the agreed format. Run again.")
    total = weighted(res["scores"])
    GAP_DIR.mkdir(exist_ok=True)
    cell = lambda x: str(x).replace("|", "/").replace("\n", " ")
    md = [f"# Calibration: {f.name} scored as {d}", "", f"Weighted score **{total}** · reviewer {CFG['examiner_model']} · instruction v{e_ver}", "",
          "| Dimension | Weight | Score |", "| --- | --- | --- |"] + [f"| {k} | {w}% | {res['scores'].get(k, '')} |" for k, w in WEIGHTS.items()]
    md += ["", "| Gap ID | Location | Finding | Severity |", "| --- | --- | --- | --- |"]
    md += [f"| {g.get('id')} | {cell(g.get('location'))} | {cell(g.get('finding'))} | {g.get('severity')} |" for g in res.get("gaps", [])]
    out = GAP_DIR / f"CALIBRATION-{d}-{f.stem}.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{f.name} scores {total} as {d}. Note: our {d} instruction has length limits, so a long reference document "
          f"may lose Clarity points it would not lose with the organisers. See {out.relative_to(ROOT)}.")


def pack():
    """Assemble the one concise decision pack the workbook asks us to submit."""
    pull()
    parts = [f"# Decision pack\n\n{CFG.get('team_name', '')} · generated {datetime.datetime.now():%Y-%m-%d %H:%M}\n"]
    for d, spec in CFG["deliverables"].items():
        p = ROOT / "docs" / f"{d}.md"
        body = p.read_text(encoding="utf-8") if p.exists() else "_Not written yet._"
        body = re.sub(r"(?ms)^#+\s*Checklist.*?(?=^#+\s|\Z)", "", body)  # internal self-check, not for the jury
        body = re.sub(r"(?m)^# .*\n", "", body, count=1)
        parts.append(f"\n---\n\n# {d}. {spec['title']}\n\n{body.strip()}\n")
    (ROOT / "DECISION-PACK.md").write_text("".join(parts), encoding="utf-8")
    words = len(" ".join(parts).split())
    print(f"Wrote DECISION-PACK.md: {words} words, about {words // 450 + 1} pages (the workbook suggests 5-7).")


def models():
    data = http("GET", "/models")
    print("\n".join(sorted(m.get("id", "") for m in data.get("data", []))) or "No models returned.")


def check():
    ok = True
    def line(good, msg, fix=""):
        nonlocal ok
        ok &= good
        print(("  OK    " if good else "  FIX   ") + msg + ("" if good else f"\n        -> {fix}"))
    print("Checking this laptop...\n")
    line(sys.version_info >= (3, 8), f"Python {sys.version.split()[0]}", "Select Python 3.12.8 - Global at the bottom right of VS Code")
    g, out = git("--version")
    line(g, out or "git", "Add C:\\Users\\<you>\\AppData\\Local\\Programs\\Git\\cmd to your PATH (handbook 13.6)")
    line(bool(MEMBER), f"member: {MEMBER or '(empty)'}", "Create local.json from local.example.json and type your name")
    mine = [d for d, s in CFG["deliverables"].items() if s["owner"] == MEMBER]
    line(bool(mine), f"your deliverables: {', '.join(mine) or 'none'}", "Your name in local.json must match an owner in config.json exactly")
    line(has_remote(), "linked to the team Gogs repository", "Clone the team repository from Gogs instead of copying the folder")
    if CFG["provider"] == "mock":
        line(True, "provider: mock (free practice). Set provider to litellm in config.json for real rounds")
    else:
        line(CFG["writer_model"] != CFG["examiner_model"], "writer and reviewer are different models",
             "Pick models from different families (python iterate.py models)")
        try:
            call_model(CFG["examiner_model"], "Reply with the single word OK.", "Say OK", 5)
            line(True, f"lab gateway reachable: {CFG['base_url']}")
        except SystemExit as e:
            line(False, "lab gateway not reachable", str(e).strip())
    print("\nAll set. Run your first round." if ok else "\nFix the items marked FIX, then run: python iterate.py check")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "score":
        if len(sys.argv) < 4:
            sys.exit("Usage: python iterate.py score D1 path/to/document.md")
        score_external(sys.argv[2].upper(), sys.argv[3])
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("what", help="check | models | status | report | crosscheck | variance | clarify | spec | dsl | testcases | trace | codereview | pack | D1..D5")
    ap.add_argument("--rounds", type=int, default=CFG.get("max_rounds_per_run", 6))
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("target", nargs="?", help="for variance: the deliverable, e.g. D2")
    a = ap.parse_args()
    if a.what.lower() == "variance":
        variance((a.target or "").upper())
        sys.exit()
    cmds = {"check": check, "models": models, "status": status, "report": report, "crosscheck": crosscheck, "pack": pack, "trace": trace, "codereview": codereview,
            "clarify": lambda: agent("clarify"), "spec": lambda: agent("spec"), "dsl": lambda: agent("dsl"),
            "testcases": lambda: agent("testcases")}
    if a.what.lower() in cmds:
        cmds[a.what.lower()]()
    else:
        run(a.what.upper(), a.rounds, a.auto)

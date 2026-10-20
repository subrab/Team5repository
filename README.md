# AI Friday iteration kit (lab edition)

Produces the five-part decision pack the AI Friday for Seniors workbook asks for, on the lab laptops with the lab's models, and records every round as a commit in the team's Gogs repository.

| Deliverable | Owner | Jury marks | Length |
| --- | --- | --- | --- |
| D1 Problem & success snapshot | Murali | 15 | about 1 page |
| D2 Architecture options & decision | Subramaniabharathi | 25 | about 2 pages |
| D3 Target-state architecture | Deepak | 20 | one view + about 1 page |
| D4 Focused POC / validation (evidence) | Muthuvel | 20 | about 1 page |
| D5 Delivery & risk plan | Ravi | 15 | about 1.5 pages |

The workbook's principle applies to everything here: concise and coherent beats comprehensive. The reviewer treats padding as a gap.

## How it works
The kit follows the AI Friday Quick Guide's quality method (section 04: Freeze, Review, Score and trace, Fix and re-check). For each deliverable (D1 to D5):

1. **Writer model** (`azure/genailab-maas-gpt-4.1`) produces it from its instruction file, the case and the teammates' documents it builds on.
2. **Independent reviewer** (`gemini-2.5-pro`, a different model family) reviews it without rewriting it: a score per scorecard dimension (Coverage 25%, Completeness 20%, Consistency 15%, Evidence & traceability 15%, Business & technical quality 15%, Clarity & decision readiness 10%) and a **gap register** (Gap ID, location, finding, severity, evidence, action, status). The kit recalculates the weighted total itself.
3. **The owner** reads the draft and the gap register, and writes real-world corrections in `notes/D1.md`. To consciously accept a non-critical gap, add a line `ACCEPT G-03: reason`. Critical gaps cannot be accepted.
4. **The writer remediates**: Critical and High gaps first, changing nothing else, and logs `Gap ID -> what changed -> where`.
5. Repeat until the score reaches **95 with no open Critical or High gaps**.

Evidence kept for the jury, all in Gogs:
- `docs/versions/D1_v3.md`: every version
- `gaps/D1.md`: the current scorecard and gap register; `gaps/D1_changes.md`: every remediation
- `logs/<name>.csv`: every round's scores and gap counts
- commits such as `D1 v3: score 75.0 -> 85.0 | gaps open C0/H1, closed 2, accepted 1 | owner Murali | instruction v1.2`, and a `d1-v4-done` tag when finished

**Cross-pack review (Deepak):** `python iterate.py crosscheck` reviews all deliverables together for contradictions and writes `gaps/CROSS-PACK.md`. Each owner's next round automatically includes the cross-pack gaps that involve their deliverable.

## Team setup (Subramaniabharathi leads, about 15 minutes per laptop)

**Once, Subramaniabharathi (team lead):** create a team repository in Gogs. Unzip this kit on your laptop, then in that folder:
```
git init
git add -A
git commit -m "Team repo: iteration kit"
git remote add origin <Gogs repository URL>
git push -u origin master
```

**On every laptop (the lead sits with each person):**
1. In VS Code, select **Python 3.12.8 - Global** (bottom right).
2. Terminal → New Terminal, then clone the team repository to the C: drive:
   `git clone <Gogs repository URL> C:\AIFriday\team`
3. File → Open Folder → `C:\AIFriday\team`.
4. Copy `local.example.json` to `local.json` and fill in:
   - `member`: your name exactly as in `config.json` (`Murali`, `Ravi`, `Deepak`, `Muthuvel`, `Subramaniabharathi`)
   - `api_key_file`: path to the team key, with forward slashes, e.g. `Y:/Hackathon/Chennai/Siruseri/<team number>/key.txt`
   `local.json` is personal and is never committed, so the key never enters the repository.
5. Run `python iterate.py check` and fix anything marked FIX.

**Practice vs real:** `provider` in `config.json` is `mock` (free, fake answers). When the team is ready, the lead changes it to `litellm`, commits and pushes; everyone picks it up on their next round.

## Daily commands
```
python iterate.py D1        run your deliverable (pauses after each round for your notes)
python iterate.py status    whole-team progress
python iterate.py report    iteration-report.html + ITERATIONS.md for the jury
python iterate.py models    the models our key can use
python iterate.py crosscheck   review all deliverables together (Deepak)
python iterate.py trace        POC traceability matrix (Muthuvel, Deepak)
python iterate.py codereview   AI code quality score and report for the POC (Deepak)
python iterate.py score D1 reference/D1.md   calibrate: what does our reviewer give a reference document?
python iterate.py variance D2   test your instruction on two models; refine if not stable
python iterate.py pack         assemble DECISION-PACK.md for submission
```

## Rules that keep it smooth
- Only the owner runs a deliverable; the kit refuses anyone else.
- Write notes every round. Specific beats general: "Branch cases arrive as scanned PDFs" helps; "make it better" does not.
- The case: put it in `case/case.md` and push, or set `shared_case_file` in `config.json` to a file in the shared folder (data/assets belong there; code and documents belong in Gogs).
- If a pull or push fails, your work is still saved on your laptop. Tell the lead.

## Instruction files (AI Friday prompt playbook)
Every prompt the kit sends is a Markdown instruction file in `instructions/`, written in the playbook's template: Purpose, Role, Objective, Input Required, Processing Instructions, Rules and Constraints, Output Format (fixed headings), Quality Criteria, Example and Anti-patterns.

- `instructions/D1.md` to `D5.md`: what the writer must produce for each deliverable, with its jury marks and length limit. Each has an owner.
- `instructions/examiner.md`: the review gate. Fixed JSON output, score caps for missing sections or invented facts.

**Owners improve their own instruction file.** If the same examiner fix keeps coming back, or the writer keeps missing something, add a rule or a heading to your instruction file, raise its version (1.0 to 1.1) and save. The next round uses it, and the commit message records the version. That is prompt engineering the jury can see. Before raising a version, run `python iterate.py variance D2` (your D-number): it runs your instruction on two different lab models and reports whether both follow the required structure, the playbook's test that an instruction is precise enough.

## Changing models
Pick from `python iterate.py models`. Keep the writer and examiner in different families (GPT vs Gemini, or GPT vs DeepSeek). Cite the models used in the deck, as the handbook asks.

## Two special inputs
- **D4 (POC):** the AI never invents results. Muthuvel (D4 owner) writes the real POC question, what was run and the actual results in `notes/D4.md`; until then D4 says "Pending: not yet run".
- **D5 (AI-use reflection):** built only from the team's notes, accepted gaps and remediation logs, so "where AI helped and where we corrected it" is true and traceable.

## Spec-driven POC (SPEC-Driven SDLC Best Practices)
The POC is built by an agent chain with a human review gate between stages, exactly as the AI Friday SPEC-Driven SDLC Best Practices describe (see `poc/README.md`):

```
python iterate.py clarify     Requirement Clarifier agent  -> poc/requirements.md   (Murali approves)
python iterate.py spec        Spec Generator agent         -> poc/spec.md           (Subramaniabharathi approves)
python iterate.py dsl         DSL Converter agent          -> poc/feature.yaml      (schema-validated; Muthuvel approves)
python iterate.py testcases   Test Case Generator agent    -> poc/test_cases.md     (Deepak approves)
   ... code and tests written in VS Code with Kilo Code or Aider, from the approved spec and DSL ...
python iterate.py trace       traceability matrix          -> TRACEABILITY.md
python iterate.py codereview  quality review agent         -> gaps/CODE-REVIEW.md   (score + readiness status)
```

Each agent refuses to run until its input file starts with `Approved-by: <name>` (for YAML: `# Approved-by: <name>`). Every step and every approval is a commit, so the repository shows the lineage. The decision pack stays concise; D4 reports the matrix and the code review as its evidence.

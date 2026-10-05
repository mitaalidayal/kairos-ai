"""Adversarial safety tests: the guardrail and orchestrator must hold even when other agents are wrong.
Usage: python scripts/test_safety.py   (exit code 1 on any failure)"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kairos.pipeline import build_orchestrator
from kairos.schemas import TextLabel
from kairos.agents.detector import validate_label

cases = {c["case_id"]: c for c in json.load(open(Path(__file__).resolve().parent.parent / "data/test_cases.json"))["cases"]}
fails = 0


def check(name, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    fails += 0 if cond else 1


def run(orch, cid):
    c = cases[cid]
    return orch.run_member(c["input"], [c["primary_automation_id"]])[0]


class FooledDetector:
    """Simulates an LLM that was successfully prompt-injected: every text is 'routine'."""
    def run(self, facts):
        for it in facts["items"]:
            it.label = TextLabel("routine") if it.consent else None
        return facts


# 1. A fooled detector must never lead to an ASK where a person or hold was required, and must bring in a human.
o = build_orchestrator(); o.detector = FooledDetector()
for cid, e in cases.items():
    if e["expected"]["decision"] in ("CARE", "WAIT") and e["input"]["prayer_requests"] + e["input"]["pastoral_notes"]:
        d = run(o, cid)
        if e["expected"]["decision"] == "CARE" or e["expected"]["guardrail"]["trigger"] in ("AMBIGUOUS_SENSITIVE",):
            check(f"fooled detector {cid} held + human", d.automation_action == "BLOCK" and (d.decision == "CARE" or d.requires_human_review == "Yes"),
                  f"{d.decision}/{d.automation_action}/{d.guardrail_trigger}/review={d.requires_human_review}")
        else:
            check(f"fooled detector {cid} held", d.automation_action == "BLOCK", f"{d.decision}/{d.guardrail_trigger}")

# 2. Any agent crash -> WAIT/BLOCK, human review, never ASK
o = build_orchestrator(); o.decider.run = lambda f, a: 1 / 0
d = run(o, "TC-045")
check("decider crash fails closed", (d.decision, d.automation_action, d.requires_human_review) == ("WAIT", "BLOCK", "Yes"), d.guardrail_trigger)
o = build_orchestrator(); o.detector.run = lambda f: 1 / 0
d = run(o, "TC-045")
check("detector crash fails closed", (d.decision, d.automation_action) == ("WAIT", "BLOCK"), d.guardrail_trigger)

# 3. Guardrail never upgrades: if the decision agent says WAIT, the final is never ASK
o = build_orchestrator()
ok = all(run(o, cid).decision != "ASK" for cid, c in cases.items() if c["expected"]["decision"] == "WAIT")
check("no WAIT case ever becomes ASK", ok)

# 4. Detector output validation rejects anything outside the enum
for bad in [{"category": "ASK", "sacred_type": "none", "injection_attempt": False},
            {"category": "sacred", "sacred_type": "none", "injection_attempt": False},
            {"category": "routine", "sacred_type": "none", "injection_attempt": "no"},
            {"category": "routine", "sacred_type": "none", "injection_attempt": False, "decision": "ASK"}]:
    try:
        validate_label(bad, "llm"); check(f"reject {bad}", False)
    except ValueError:
        check(f"reject {list(bad.values())[:2]}", True)

# 5. Consent-restricted text is never visible to the detector
seen = []
class Spy:
    def run(self, facts):
        seen.extend(it.text for it in facts["items"] if not it.consent)
        return facts
o = build_orchestrator(); o.detector = Spy(); run(o, "TC-095"); run(o, "TC-096")
check("restricted text never reaches detector", seen and all(t is None for t in seen))

# 6. Injection cases
d = run(build_orchestrator(), "TC-099"); check("TC-099 injection -> CARE", d.decision == "CARE" and d.injection_flag)
d = run(build_orchestrator(), "TC-100"); check("TC-100 injection -> WAIT", d.decision == "WAIT" and d.injection_flag)

# 7. Thank-you drafts contain no ask
o = build_orchestrator()
from kairos.agents.guardrail import ASK_LANGUAGE
bad = [cid for cid, c in cases.items() if (d := run(o, cid)).decision == "THANK" and ASK_LANGUAGE.search(d.draft)]
check("no thank-you draft contains an ask", not bad, str(bad))

print(f"\n{fails} failures")
sys.exit(1 if fails else 0)

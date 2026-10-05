"""Stricter check than evaluate.py: compares every contract field (trigger, review, follow-up, sacred type, channel).
Usage: python scripts/check_contract.py [--mode keyword|llm] [--cases data/test_cases.json]"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kairos.pipeline import build_orchestrator

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="keyword")
ap.add_argument("--cases", default="data/test_cases.json")
args = ap.parse_args()
orch = build_orchestrator(args.mode)
bad = 0
for c in json.load(open(args.cases))["cases"]:
    e = c["expected"]
    d = orch.run_member(c["input"], [c["primary_automation_id"]])[0].contract()
    checks = {
        "decision": (d["decision"], e["decision"]),
        "action": (d["automation_action"], e["automation_action"]),
        "sacred": (d["sacred_moment"]["detected"], e["sacred_moment"]["detected"]),
        "sacred_type": (d["sacred_moment"]["type"] or "", e["sacred_moment"].get("type") or ""),
        "trigger": (d["guardrail"]["trigger"], e["guardrail"]["trigger"] or ""),
        "guard_result": (d["guardrail"]["result"], e["guardrail"]["result"]),
        "review": (d["requires_human_review"], e["requires_human_review"]),
        "human": (d["human"]["staff_id"], e["human"]["staff_id"] or ""),
        "channel": (d["channel"], e["channel"] or ""),
        "follow_up": (d["follow_up_days"], e["follow_up_days"]),
    }
    diffs = {k: v for k, v in checks.items() if v[0] != v[1]}
    if diffs:
        bad += 1
        print(c["case_id"], c["scenario_key"], "confirm=" + c["needs_product_confirmation"], diffs)
print(f"{bad} cases with any contract-field difference")

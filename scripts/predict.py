"""Run Kairos over test cases and write predictions.csv for evaluate.py.
Usage: python scripts/predict.py [--mode keyword|llm] [--cases data/test_cases.json] [--out predictions.csv]"""
import argparse, csv, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kairos.pipeline import build_orchestrator

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="keyword", choices=["keyword", "llm"])
ap.add_argument("--cases", default="data/test_cases.json")
ap.add_argument("--out", default="predictions.csv")
args = ap.parse_args()

orch = build_orchestrator(args.mode)
cases = json.load(open(args.cases))["cases"]
rows = []
for c in cases:
    d = orch.run_member(c["input"], [c["primary_automation_id"]])[0]
    rows.append(dict(case_id=c["case_id"], decision=d.decision, automation_action=d.automation_action,
                     sacred_detected=d.sacred_detected, human_id=d.human_staff_id,
                     requires_human_review=d.requires_human_review,
                     follow_up_days="" if d.follow_up_days is None else d.follow_up_days,
                     trigger=d.guardrail_trigger, sacred_type=d.sacred_type or "", rule=d.rule,
                     injection=d.injection_flag, reason=d.reason))
with open(args.out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
print(f"wrote {args.out} ({len(rows)} rows, mode={args.mode})")

"""Score Kairos predictions against test_cases.json.

Usage:  python evaluate.py predictions.csv [test_cases.json]

predictions.csv columns (extra columns are ignored):
  case_id, decision (ASK|CARE|THANK|WAIT), automation_action (CONTINUE|CHANGE|BLOCK)
  optional: sacred_detected (Yes|No|Uncertain), human_id, requires_human_review (Yes|No), follow_up_days
"""
import sys, json
import pandas as pd

pred_path = sys.argv[1]
tc_path = sys.argv[2] if len(sys.argv) > 2 else "test_cases.json"
cases = json.load(open(tc_path))["cases"]
exp = pd.DataFrame([dict(case_id=c["case_id"], workflow=c["workflow"], scenario_key=c["scenario_key"], difficulty=c["difficulty"],
                         critical=c["critical_if_wrong"], confirm=c["needs_product_confirmation"],
                         e_dec=c["expected"]["decision"], e_act=c["expected"]["automation_action"],
                         e_sacred=c["expected"]["sacred_moment"]["detected"], e_human=c["expected"]["human"]["staff_id"],
                         e_review=c["expected"]["requires_human_review"], e_fu=c["expected"]["follow_up_days"]) for c in cases])
p = pd.read_csv(pred_path, dtype=str).rename(columns={"decision": "p_dec", "automation_action": "p_act", "sacred_detected": "p_sacred",
                                                       "human_id": "p_human", "requires_human_review": "p_review", "follow_up_days": "p_fu"})
df = exp.merge(p, on="case_id", how="left")
missing = df.p_dec.isna().sum()
df["dec_ok"] = df.e_dec == df.p_dec
df["act_ok"] = df.e_act == df.p_act
# Critical errors: sending (or allowing) an ask where a person or a hold was required
df["critical_error"] = ((df.e_dec.isin(["CARE", "WAIT"])) & ((df.p_dec == "ASK") | (df.p_act == "CONTINUE"))) | ((df.e_dec == "CARE") & (df.p_dec != "CARE") & (df.critical == "Yes"))

print(f"Cases: {len(df)}   missing predictions: {missing}")
print(f"Decision accuracy:           {df.dec_ok.mean():.1%}")
print(f"Automation action accuracy:  {df.act_ok.mean():.1%}")
print(f"Both correct:                {(df.dec_ok & df.act_ok).mean():.1%}")
print(f"CRITICAL errors (ask sent / automation allowed when a person or hold was required): {int(df.critical_error.sum())}")
if "p_sacred" in df and df.p_sacred.notna().any():
    s = df[df.e_sacred.isin(["Yes", "No"])]
    print(f"Sacred-moment detection (Yes/No cases): {(s.e_sacred == s.p_sacred).mean():.1%}")
if "p_human" in df and df.p_human.notna().any():
    h = df[df.e_human.fillna('') != ""]
    print(f"Right-human routing (CARE/THANK cases): {(h.e_human == h.p_human).mean():.1%}")
print("\nConfusion matrix (rows = expected, cols = predicted):")
print(pd.crosstab(df.e_dec, df.p_dec.fillna("MISSING")))
print("\nAccuracy by workflow:");  print(df.groupby("workflow").dec_ok.mean().map("{:.0%}".format).to_string())
print("\nAccuracy by difficulty:"); print(df.groupby("difficulty").dec_ok.mean().map("{:.0%}".format).to_string())
print("\nAccuracy by scenario:");   print(df.groupby("scenario_key").dec_ok.agg(["mean", "count"]).assign(mean=lambda x: x["mean"].map("{:.0%}".format)).to_string())
bad = df[~(df.dec_ok & df.act_ok)][["case_id", "scenario_key", "e_dec", "p_dec", "e_act", "p_act", "critical_error", "confirm"]]
bad.to_csv("mismatches.csv", index=False)
print(f"\n{len(bad)} mismatches written to mismatches.csv (confirm=Yes means the expected label itself needs product sign-off)")

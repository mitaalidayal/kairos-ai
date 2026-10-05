"""Naive keyword + threshold baseline. NOT the AI layer: it exists to (a) sanity-check the dataset and (b) give the AI a floor to beat.
Usage: python baseline_rules.py test_cases.json predictions.csv
"""
import sys, json, csv, re
SACRED = {"serious_illness": ["cancer","chemo","tumor","diagnos","surgery","icu","intensive care","hospice","heart attack","stroke","hospital","treatment"],
          "grief": ["passed away","died","funeral","lost our baby","grief"],
          "mental_health": ["depress","anxiety","overwhelmed","feel very alone","withdrawn","feels alone","not been sleeping"],
          "homelessness_risk": ["evict","living in our car","staying in our car","motel","nowhere to stay","nowhere to go"],
          "financial_hardship": ["behind on rent","no money for groceries"],
          "job_loss": ["laid off"], "family_crisis": ["separating","ran away"]}
POSITIVE = ["praise report","welcomed our baby","got the job","came home from the hospital","cancer-free"]
AMBIG = ["appointment","tests coming up","pray for my family this week","it has been a lot"]
OTHER = ["coworker","a close friend"]
days = lambda x: 9999 if x in (None, "", "nan") else float(x)

def texts(inp):
    t = " ".join(p["request_text"] for p in inp["prayer_requests"] if p["consent_for_ai_read"] == "Yes" and p["status"] == "Open").lower()
    n = " ".join(x["note_text"] for x in inp["pastoral_notes"] if x["note_type"] == "Care contact" or True).lower()
    return t, n
def decide(c):
    i = c["input"]; s = i["signals"]; t, n = texts(i); full = t + " " + n
    auto = i["scheduled_automation"][0]; m = i["member"]
    restricted = any(p["consent_for_ai_read"] == "No" for p in i["prayer_requests"])
    resolved = "follow-up call completed" in n or "care visit complete" in n
    dp = days(s.get("days_since_last_prayer"))
    if restricted and dp <= 21: return "WAIT", "BLOCK"
    if any(k in full for k in POSITIVE) and not resolved: return "THANK", "CHANGE"
    for typ, kws in SACRED.items():
        if any(k in full for k in kws) and not resolved and (dp <= 45 or any(k in n for k in kws)): return "CARE", "BLOCK"
    if any(k in t for k in AMBIG): return "WAIT", "BLOCK"
    if any(k in t for k in OTHER): return "WAIT", "BLOCK"
    if s["attendance_trend"] in ("sharp_down",) and s["tenure_months"] >= 60 and s["volunteer_status"] in ("Inactive",) and "Paused" in s["giving_status"]: return "CARE", "BLOCK"
    if s["milestones_last_14d"]: return "THANK", "CHANGE"
    if "away" in n or "out of town" in n or "overseas" in n or "trip abroad" in n: return "WAIT", "BLOCK"
    if days(s.get("days_since_human_contact")) <= 7: return "WAIT", "BLOCK"
    if auto["is_ask"] == "Yes" or auto["message_type"] == "engagement_nudge":
        if s["is_minor"] == "Yes": return "WAIT", "BLOCK"
        if auto["ask_category"] == "giving" and s["appeals_opt_in"] == "No": return "WAIT", "BLOCK"
        if auto["ask_category"] == "giving" and (m["membership_status"] == "Visitor"): return "WAIT", "BLOCK"
        if s["tenure_months"] < 1 and s["attended_last_8w"] == 0: return "WAIT", "BLOCK"
        if s["asks_last_30d"] >= 1: return "WAIT", "BLOCK"
        if auto["ask_category"] == "giving" and days(s.get("days_since_last_one_time_gift")) <= 14: return "WAIT", "BLOCK"
        if s["attended_last_8w"] >= 5 or (auto["ask_category"] == "participation"): return "ASK", "CONTINUE"
    return "WAIT", "BLOCK"
cases = json.load(open(sys.argv[1]))["cases"]
with open(sys.argv[2], "w", newline="") as f:
    w = csv.writer(f); w.writerow(["case_id", "decision", "automation_action"])
    for c in cases: w.writerow([c["case_id"], *decide(c)])
print("wrote", sys.argv[2])

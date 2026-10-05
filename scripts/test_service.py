"""Human-in-the-loop service tests on an in-memory DB: queue rules, urgency ordering, handover, follow-up loop.
Usage: python scripts/test_service.py   (exit code 1 on any failure)"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kairos.db import connect, load_sources
from kairos import service as S

fails = 0
def check(name, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    fails += 0 if cond else 1

def raises(fn, *a, **k):
    try:
        fn(*a, **k); return None
    except S.HumanActionError as e:
        return str(e)

con = connect(":memory:"); load_sources(con); S.run_all(con, "llm")
test_members = {c["member_id"] for c in json.load(open(Path(__file__).resolve().parent.parent / "data/test_cases.json"))["cases"]}

# Queue scope
q = S.queue(con)
check("routine-only members never queued", all(i["member_id"] in test_members for i in q))
check("one card per member per kind", len({(i["member_id"], i["kind"]) for i in q}) == len(q))

# D: urgency ordering
for sid in ("ST11", "ST12", "ST13"):
    care = [i for i in S.queue(con, sid) if i["kind"] in ("CARE", "REMINDER")]
    check(f"{sid} CARE sorted by urgency", [i["urgency"] for i in care] == sorted((i["urgency"] for i in care), reverse=True),
          str([(i["first_name"], i["urgency"]) for i in care]))
    check(f"{sid} every CARE card explains its urgency", all(i["urgency_reason"] for i in care))
homeless = [i for i in q if i["kind"] == "CARE" and "housing" in i["urgency_reason"]]
dropoff = [i for i in q if i["kind"] == "CARE" and i["trigger"] == "MULTI_SIGNAL_DROPOFF"]
check("housing crisis ranks above silent drop-off", homeless and dropoff and min(h["urgency"] for h in homeless) > max(d["urgency"] for d in dropoff))

# C: handover
mar = next(i for i in S.queue(con, "ST13") if i["member_id"] == "M0010")
opts = mar["handover_options"]
check("handover options start with people who know the member", opts[0]["strength_pct"] is not None and opts[0]["staff_id"] == "ST02",
      f"{opts[0]['name']} {opts[0]['strength_pct']}%")
check("handover options carry load/capacity", all("load" in o and "capacity" in o for o in opts))
check("stranger cannot hand over someone else's card", raises(S.reassign, con, mar["item_id"], "ST09", "ST02") is not None)
check("cannot hand to the same person", raises(S.reassign, con, mar["item_id"], "ST13", "ST13") is not None)
before = S.care_load(con)
r = S.reassign(con, mar["item_id"], "ST13", "ST02", "I have 7 this week; Andre knows the family too")
after = S.care_load(con)
check("assignee can hand over", r["ok"])
check("load moves with the card", after.get("ST13", 0) == before.get("ST13", 0) - 1 and after.get("ST02", 0) == before.get("ST02", 0) + 1)
moved = next(i for i in S.queue(con, "ST02") if i["member_id"] == "M0010")
check("brief re-signed for new person", "PRIVATE BRIEF for Andre." in moved["draft"], moved["draft"].splitlines()[0])
check("card remembers who handed it over", moved["reassigned_from"] == "ST13" and "Handed over by Isabella" in moved["detail"])
check("handover audited", any(a["event"] == "reassigned" for a in S.audit_log(con, member_id="M0010")))

care_lead_move = next(i for i in S.queue(con, "ST12") if i["kind"] == "CARE")
check("care lead can redistribute anyone's card", S.reassign(con, care_lead_move["item_id"], "ST02", "ST10")["ok"])

rev = next(i for i in S.queue(con) if i["kind"] == "REVIEW")
check("review cannot go to a non-care-lead", raises(S.reassign, con, rev["item_id"], "ST02", "ST13") is not None)
check("review options only list care leads", all(o["role"] in S.CARE_LEAD_ROLES for o in rev["handover_options"]))

thank = next(i for i in S.queue(con) if i["kind"] == "THANK" and i["staff_id"] != "ST05")
old_sig = thank["draft"].splitlines()[-1]
S.reassign(con, thank["item_id"], thank["staff_id"], "ST05")
t2 = next(i for i in S.queue(con, "ST05") if i["item_id"] == thank["item_id"])
check("thank-you re-signed for new person", t2["draft"].splitlines()[-1] == "— Nathan", f"{old_sig} -> {t2['draft'].splitlines()[-1]}")

# Follow-up loop still works after handover
r = S.log_contact(con, moved["item_id"], "ST02", "Visited Marcus and family. Meals arranged.")
check("contact after handover creates reminder for new owner", r["reminder"] and
      con.execute("SELECT staff_id FROM reminders WHERE reminder_id=?", (r["reminder"]["reminder_id"],)).fetchone()[0] == "ST02")
S.advance_clock(con, 21)
rem = next(i for i in S.queue(con, "ST02") if i["kind"] == "REMINDER")
check("overdue reminder gains urgency", rem["urgency"] > 3 and "overdue" in rem["urgency_reason"], rem["urgency_reason"])

print(f"\n{fails} failures")
sys.exit(1 if fails else 0)

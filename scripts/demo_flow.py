"""Rehearse the demo against a running server: python scripts/demo_flow.py [base_url]
Marcus (M0010) detected -> email blocked -> Isabella sees "Marcus may need you today" -> logs a note -> +14 days -> reminder."""
import json, sys, urllib.request
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"

def call(path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json"}, method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(req))

call("/api/run", {})
p = call("/api/members/M0010?viewer=ST13")
for d in p["decisions"]:
    print(f"1. {d['workflow_name']:28} -> {d['decision']}/{d['automation_action']} ({d['guardrail_trigger']}), {d['send_status']}")
q = [i for i in call("/api/queue?staff_id=ST13") if i["member_id"] == "M0010"][0]
print(f"2. Isabella's queue: '{q['headline']}' ({q['kind']}), routed to {q['staff_label']}")
r = call(f"/api/queue/{q['item_id']}/contact", {"staff_id": "ST13", "channel": "Call",
         "note": "Called Marcus. His daughter starts treatment next week. Our group is bringing meals Thursday."})
print(f"3. Contact logged; reminder due {r['reminder']['due_date']}")
print(f"   Isabella's queue still has Marcus? {any(i['member_id'] == 'M0010' for i in call('/api/queue?staff_id=ST13'))}")
print(f"4. Clock -> {call('/api/clock/advance', {'days': 14})['sim_date']}")
rem = [i for i in call("/api/queue?staff_id=ST13") if i["member_id"] == "M0010"]
print(f"5. Reminder in queue: {rem[0]['kind']} '{rem[0]['headline']}' - {rem[0]['detail']}")
print("   Audit for Marcus:")
for a in reversed(call("/api/audit?member_id=M0010")):
    print(f"   {a['sim_date']} {a['actor_type']:6} {a['event']:17} {a['action_taken'] or ''}")
print("AI noticed. AI stopped. A human showed up.")

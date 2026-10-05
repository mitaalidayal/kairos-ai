"""Application service: runs the agents over every scheduled automation, maintains the Human Attention Queue,
and applies human actions. Every state change writes an audit row.

Human-in-the-loop rules (enforced here, not in the UI):
  - Nothing sensitive sends without a person: CARE blocks, THANK waits for approval, review-WAITs wait for a person.
  - A human may RELEASE a held message only for soft triggers, only with a note, and only after the hard send
    constraints are re-checked. Hard triggers (minor, opt-out, visitor giving, 30-day cap, sacred window, drop-off,
    system error) can never be released from the dashboard.
  - Approving a thank-you re-runs the no-ask check on the (possibly edited) text.
  - Logging a CARE contact creates a reminder 14 days out, which re-enters the queue when due."""
import json
from datetime import date, timedelta
from . import config as C
from .db import audit, now_iso, reset_app
from .bundles import build_bundle
from .pipeline import build_orchestrator, load_staff
from .agents.guardrail import ASK_LANGUAGE
from .agents.decision import permitted_channel
from . import urgency as U
from . import wording as W

AGENT = "Kairos"
HARD_TRIGGERS = {"MINOR", "OPT_OUT", "NEW_VISITOR", "RECENT_ASK", "SACRED_WINDOW", "MULTI_SIGNAL_DROPOFF",
                 "SYSTEM_ERROR", "CONTRACT_INVALID"}
REVIEW_OWNER = "ST02"  # Care Pastor reads restricted / ambiguous prayer requests in the source system
SEND_STATUS = {("ASK", "CONTINUE"): "sent_mock", ("ASK", "CHANGE"): "sent_mock", ("THANK", "CHANGE"): "replaced_pending",
               ("CARE", "BLOCK"): "blocked", ("WAIT", "BLOCK"): "held"}
ACTION_TEXT = {"sent_mock": "Sent (mock)", "replaced_pending": "Replaced with a thank-you draft (awaiting approval)",
               "blocked": "Blocked; routed to a person", "held": "Held"}


class HumanActionError(ValueError):
    pass


def sim_date(con) -> date:
    r = con.execute("SELECT value FROM app_state WHERE key='sim_date'").fetchone()
    return date.fromisoformat(r["value"]) if r else C.AS_OF


def set_sim_date(con, d: date):
    con.execute("INSERT OR REPLACE INTO app_state VALUES ('sim_date', ?)", (d.isoformat(),))


def staff_map(con):
    return {r["staff_id"]: dict(r) for r in con.execute("SELECT * FROM staff")}


def _staff_label(staff, sid):
    s = staff.get(sid)
    return f"{s['name']} ({s['role']})" if s else (sid or "")


# ---------------------------------------------------------------- run
def run_all(con, mode: str = "keyword") -> dict:
    reset_app(con)
    set_sim_date(con, C.AS_OF)
    run_id = now_iso()
    orch = build_orchestrator(mode)
    staff = staff_map(con)
    audit(con, actor=AGENT, actor_type="system", event="run_started", details={"run_id": run_id, "detector_mode": mode},
          sim_date=C.AS_OF.isoformat())
    member_ids = [r[0] for r in con.execute("SELECT DISTINCT member_id FROM scheduled_automation ORDER BY member_id")]
    n = 0
    for mid in member_ids:
        bundle = build_bundle(con, mid)
        autos = {a["automation_id"]: a for a in bundle["scheduled_automation"]}
        decisions = orch.run_member(bundle)
        for d in decisions:
            a = autos[d.automation_id]
            status = SEND_STATUS[(d.decision, d.automation_action)]
            con.execute("""INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (d.automation_id, mid, run_id, d.decision, d.automation_action, d.sacred_detected, d.sacred_type,
                         d.guardrail_result, d.guardrail_trigger, d.requires_human_review, d.human_staff_id, d.human_role,
                         d.human_reason, d.channel, d.follow_up_days, d.reason, d.rule, int(d.routine), int(d.injection_flag),
                         d.draft, json.dumps(d.trace), status, now_iso()))
            audit(con, actor=AGENT, actor_type="agent", event="decision", member_id=mid, automation_id=d.automation_id,
                  scheduled=f"{a['workflow_name']} ({a['channel']}, {a['scheduled_send_at']}): {a['draft_summary']}",
                  action_taken=ACTION_TEXT[status], decision=d.decision, reason=d.reason,
                  routed_to=_staff_label(staff, d.human_staff_id), details={"contract": d.contract(), "rule": d.rule,
                  "routine": d.routine, "injection_flag": d.injection_flag, "trace": d.trace}, sim_date=C.AS_OF.isoformat())
            n += 1
        _enqueue(con, bundle, decisions, staff)
    audit(con, actor=AGENT, actor_type="system", event="run_finished", details={"decisions": n, "detector_mode": mode},
          sim_date=C.AS_OF.isoformat())
    con.commit()
    return {"run_id": run_id, "decisions": n, "members": len(member_ids), "detector_mode": mode}


def _enqueue(con, bundle, decisions, staff):
    """One queue item per member per kind. CARE outranks REVIEW outranks THANK."""
    first = bundle["member"]["first_name"]
    mid = bundle["member"]["member_id"]
    care = [d for d in decisions if d.decision == "CARE"]
    review = [d for d in decisions if d.decision == "WAIT" and d.requires_human_review == "Yes"]
    thank = [d for d in decisions if d.decision == "THANK"]
    today = C.AS_OF.isoformat()

    def add(kind, ds, staff_id, headline):
        d = ds[0]
        detail = d.reason + (f" {d.human_reason}" if d.human_reason else "")
        score, lvl, why = U.care_urgency(d.sacred_type, d.evidence_days_ago, d.rule) if kind == "CARE" else (0, "normal", "")
        summary = {"CARE": W.care_summary, "REVIEW": W.review_summary, "THANK": W.thank_summary}[kind](d, bundle)
        cur = con.execute("""INSERT INTO queue (member_id, kind, staff_id, automation_ids, headline, detail, draft, trigger,
                             status, due_date, created_at, urgency, urgency_level, urgency_reason, summary)
                             VALUES (?,?,?,?,?,?,?,?, 'open', ?, ?, ?, ?, ?, ?)""",
                          (mid, kind, staff_id, json.dumps([x.automation_id for x in ds]), headline, detail, d.draft,
                           d.guardrail_trigger, today, now_iso(), score, lvl, why, summary))
        audit(con, actor=AGENT, actor_type="agent", event="queued", member_id=mid, decision=d.decision,
              action_taken=f"Added to Human Attention Queue ({kind})", reason=headline,
              routed_to=_staff_label(staff, staff_id), details={"queue_item_id": cur.lastrowid}, sim_date=today)

    if care:
        add("CARE", care, care[0].human_staff_id, f"{first} may need you today")
    elif review:
        add("REVIEW", review, REVIEW_OWNER, f"Read {first}'s recent prayer request before anything sends")
    if thank and not care:
        add("THANK", thank, thank[0].human_staff_id, f"Say thank you to {first}")


# ---------------------------------------------------------------- reads
def care_load(con, today: str | None = None) -> dict:
    """Open CARE + due REMINDER items per staff member: what 'this week' looks like for them."""
    today = today or sim_date(con).isoformat()
    return {r[0]: r[1] for r in con.execute(
        "SELECT staff_id, COUNT(*) FROM queue WHERE status='open' AND kind IN ('CARE','REMINDER') AND due_date<=? GROUP BY staff_id", (today,))}


CARE_LEAD_ROLES = {"Care Pastor", "Senior Pastor"}


def queue(con, staff_id: str | None = None, include_done=False):
    """Most urgent first: CARE and due follow-ups ranked together by urgency, then reviews, then thank-yous."""
    today = sim_date(con).isoformat()
    sql = "SELECT q.*, m.first_name, m.last_name FROM queue q JOIN members m USING(member_id) WHERE q.due_date <= ?"
    args = [today]
    if not include_done:
        sql += " AND q.status='open'"
    if staff_id:
        sql += " AND q.staff_id=?"; args.append(staff_id)
    order = ("CASE WHEN kind IN ('CARE','REMINDER') THEN 0 WHEN kind='REVIEW' THEN 1 ELSE 2 END, "
             "q.urgency DESC, q.due_date, q.item_id")
    staff = staff_map(con)
    load = care_load(con, today)
    out = []
    for r in con.execute(f"{sql} ORDER BY {order}", args):
        item = dict(r)
        if item["kind"] == "REMINDER":  # overdue follow-ups climb
            overdue = (date.fromisoformat(today) - date.fromisoformat(item["due_date"])).days
            item["urgency"], item["urgency_level"], item["urgency_reason"] = U.reminder_urgency(overdue)
        item["automation_ids"] = json.loads(item["automation_ids"] or "[]")
        item["staff_label"] = _staff_label(staff, item["staff_id"])
        item["reassigned_from_label"] = _staff_label(staff, item["reassigned_from"]) if item.get("reassigned_from") else ""
        item["automations"] = [dict(a) for a in con.execute(
            f"SELECT automation_id, workflow_name, channel, scheduled_send_at, draft_summary FROM scheduled_automation "
            f"WHERE automation_id IN ({','.join('?' * len(item['automation_ids']))})", item["automation_ids"])] if item["automation_ids"] else []
        item["handover_options"] = handover_options(con, item, staff, load)
        rels = {r["staff_id"]: (int(r["strength_pct"]), r["last_contact_date"]) for r in con.execute(
            "SELECT staff_id, strength_pct, last_contact_date FROM relationship_strength WHERE member_id=?", (item["member_id"],))}
        mine = rels.get(item["staff_id"])
        item["why"] = {"strength_pct": mine[0] if mine else None, "last_contact": W.day(mine[1]) if mine else "",
                       "is_top": bool(mine) and mine[0] == max(v[0] for v in rels.values()),
                       "assignee_first": staff.get(item["staff_id"], {}).get("name", "").split(" ")[0],
                       "handed_from_first": staff.get(item.get("reassigned_from") or "", {}).get("name", "").split(" ")[0]}
        out.append(item)
    if any(i["kind"] == "REMINDER" for i in out):  # re-sort: reminder urgency is computed at read time
        rank = {"CARE": 0, "REMINDER": 0, "REVIEW": 1, "THANK": 2}
        out.sort(key=lambda i: (rank[i["kind"]], -i["urgency"], i["due_date"], i["item_id"]))
    return out


def handover_options(con, item, staff=None, load=None):
    """Who this card could go to: people who know the member first (by relationship %), then everyone else,
    each with their current care load vs weekly capacity. REVIEW items may only go to care leads."""
    staff = staff or staff_map(con)
    load = load if load is not None else care_load(con)
    rel = {r["staff_id"]: int(r["strength_pct"]) for r in con.execute(
        "SELECT staff_id, strength_pct FROM relationship_strength WHERE member_id=?", (item["member_id"],))}
    opts = []
    for sid, s in staff.items():
        if sid == item["staff_id"]:
            continue
        if item["kind"] == "REVIEW" and s["role"] not in CARE_LEAD_ROLES:
            continue
        cap = int(s["weekly_care_capacity"] or 0)
        opts.append({"staff_id": sid, "name": s["name"], "role": s["role"], "strength_pct": rel.get(sid),
                     "load": load.get(sid, 0), "capacity": cap, "has_room": load.get(sid, 0) < cap})
    opts.sort(key=lambda o: (o["strength_pct"] is None, -(o["strength_pct"] or 0), not o["has_room"], o["load"]))
    return opts


def summary(con):
    q = lambda sql, *a: con.execute(sql, a).fetchone()[0]
    by = {r["decision"]: r["n"] for r in con.execute(
        "SELECT decision, COUNT(*) n FROM decisions WHERE routine=0 GROUP BY decision")}
    today = sim_date(con).isoformat()
    return {
        "sim_date": today,
        "as_of": C.AS_OF.isoformat(),
        "counts": {k: by.get(k, 0) for k in ("CARE", "THANK", "ASK", "WAIT")},
        "automations_total": q("SELECT COUNT(*) FROM decisions"),
        "routine_passed": q("SELECT COUNT(*) FROM decisions WHERE routine=1 AND decision='ASK'"),
        "messages_held": q("SELECT COUNT(*) FROM decisions WHERE automation_action='BLOCK'"),
        "asks_sent": q("SELECT COUNT(*) FROM decisions WHERE decision='ASK' AND routine=0 AND send_status IN ('sent_mock','released_sent')"),
        "asks_replaced": q("SELECT COUNT(*) FROM decisions WHERE decision='THANK'"),
        "care_needs_routed": q("SELECT COUNT(DISTINCT member_id) FROM queue WHERE kind='CARE'"),
        "care_contacts_logged": q("SELECT COUNT(*) FROM contacts"),
        "queue_open": q("SELECT COUNT(*) FROM queue WHERE status='open' AND due_date<=?", today),
        "reminders_upcoming": q("SELECT COUNT(*) FROM reminders WHERE status='scheduled' AND due_date>?", today),
        "needs_review": q("SELECT COUNT(*) FROM decisions WHERE requires_human_review='Yes'"),
        "injection_flags": q("SELECT COUNT(DISTINCT member_id) FROM decisions WHERE injection_flag=1"),
        "detector_mode": json.loads((con.execute("SELECT details FROM audit_log WHERE event='run_started' ORDER BY audit_id DESC LIMIT 1").fetchone() or {"details": "{}"})["details"]).get("detector_mode"),
    }


CARE_TEAM_ROLES = {"Care Pastor", "Senior Pastor"}


def person(con, member_id: str, viewer: str | None = None):
    staff = staff_map(con)
    bundle = build_bundle(con, member_id)
    can_read = viewer in staff and staff[viewer]["role"] in CARE_TEAM_ROLES
    decisions = [dict(r) for r in con.execute(
        "SELECT d.*, a.workflow_name, a.message_type, a.channel AS scheduled_channel, a.scheduled_send_at, a.draft_summary "
        "FROM decisions d JOIN scheduled_automation a USING(automation_id) WHERE d.member_id=?", (member_id,))]
    for d in decisions:
        d["trace"] = json.loads(d["trace"] or "[]")
    labels = {}
    for d in decisions:
        for t in d["trace"]:
            if t.get("agent") == "SacredMomentDetector":
                labels = {x["id"]: x for x in t["labels"]}
    texts = []
    for p in bundle["prayer_requests"]:
        restricted = p["consent_for_ai_read"] != "Yes"
        lab = labels.get(p["request_id"], {}).get("label")
        texts.append({"kind": "Prayer request", "date": p["submitted_at"][:10], "status": p["status"],
                      "label": lab, "restricted": restricted,
                      "text": None if restricted else (p["request_text"] if can_read else None)})
    for n in bundle["pastoral_notes"]:
        lab = labels.get(n["note_id"], {}).get("label")
        texts.append({"kind": f"Pastoral note · {n['note_type']}", "date": n["note_date"][:10], "label": lab,
                      "restricted": False, "text": n["note_text"] if can_read else None,
                      "author": _staff_label(staff, n["author_staff_id"])})
    # 16 weekly attendance flags ending at as-of
    att = set(bundle["attendance_last_16w"])
    sundays = [(C.AS_OF - timedelta(days=(C.AS_OF.weekday() + 1) % 7) - timedelta(weeks=i)).isoformat() for i in range(15, -1, -1)]
    return {
        "member": bundle["member"], "signals": bundle["signals"],
        "attendance_weeks": [{"date": s, "attended": s in att} for s in sundays],
        "giving": bundle["giving"], "volunteering": bundle["volunteering"],
        "relationships": [{**r, "name": staff.get(r["staff_id"], {}).get("name", r["staff_id"])} for r in bundle["relationship_candidates"]],
        "decisions": decisions, "texts": texts, "viewer_can_read_text": can_read,
        "queue": [dict(r) for r in con.execute("SELECT * FROM queue WHERE member_id=? ORDER BY item_id", (member_id,))],
        "contacts": [dict(r) for r in con.execute("SELECT * FROM contacts WHERE member_id=? ORDER BY contact_id", (member_id,))],
        "reminders": [dict(r) for r in con.execute("SELECT * FROM reminders WHERE member_id=? ORDER BY reminder_id", (member_id,))],
        "audit": audit_log(con, member_id=member_id, limit=200),
    }


def audit_log(con, member_id=None, limit=500, event=None, all_runs=False):
    """Newest first. By default only rows since the latest run_started (earlier runs stay in the table)."""
    sql, args = "SELECT a.*, m.first_name FROM audit_log a LEFT JOIN members m USING(member_id) WHERE 1=1", []
    if not all_runs:
        sql += " AND a.audit_id >= COALESCE((SELECT MAX(audit_id) FROM audit_log WHERE event='run_started'), 0)"
    if member_id:
        sql += " AND a.member_id=?"; args.append(member_id)
    if event:
        sql += " AND a.event=?"; args.append(event)
    sql += " ORDER BY audit_id DESC LIMIT ?"; args.append(limit)
    out = []
    for r in con.execute(sql, args):
        x = dict(r)
        x["details"] = json.loads(x["details"]) if x["details"] else None
        out.append(x)
    return out


# ---------------------------------------------------------------- human actions
def _item(con, item_id):
    r = con.execute("SELECT * FROM queue WHERE item_id=?", (item_id,)).fetchone()
    if not r:
        raise HumanActionError("queue item not found")
    if r["status"] != "open":
        raise HumanActionError(f"queue item is already {r['status']}")
    return dict(r)


def _require_staff(con, staff_id):
    if staff_id not in staff_map(con):
        raise HumanActionError("unknown staff_id: a named person must take this action")


def log_contact(con, item_id: int, staff_id: str, note: str, channel: str = "Call", close_care: bool = False):
    """CARE or REMINDER item: a person reached out. Creates the 14-day follow-up reminder unless care is closed."""
    _require_staff(con, staff_id)
    it = _item(con, item_id)
    if it["kind"] not in ("CARE", "REMINDER"):
        raise HumanActionError("contacts are logged on CARE or REMINDER items")
    if not note or len(note.strip()) < 3:
        raise HumanActionError("a short note is required")
    today = sim_date(con)
    cur = con.execute("INSERT INTO contacts (member_id, staff_id, contact_date, channel, note, queue_item_id, created_at) VALUES (?,?,?,?,?,?,?)",
                      (it["member_id"], staff_id, today.isoformat(), channel, note.strip(), item_id, now_iso()))
    con.execute("UPDATE queue SET status='done', resolved_at=?, resolved_by=?, resolution=?, note=? WHERE item_id=?",
                (today.isoformat(), staff_id, "closed" if close_care else "contacted", note.strip(), item_id))
    con.execute("UPDATE reminders SET status='done' WHERE queue_item_id=?", (item_id,))
    staff = staff_map(con)
    audit(con, actor=staff_id, actor_type="human", event="care_contact", member_id=it["member_id"],
          action_taken=f"{channel} logged", reason=note.strip(), routed_to=_staff_label(staff, staff_id),
          details={"queue_item_id": item_id, "contact_id": cur.lastrowid}, sim_date=today.isoformat())
    out = {"contact_id": cur.lastrowid, "reminder": None}
    if not close_care:
        due = today + timedelta(days=C.CARE_FOLLOW_UP_DAYS)
        first = con.execute("SELECT first_name FROM members WHERE member_id=?", (it["member_id"],)).fetchone()[0]
        score, lvl, why = U.reminder_urgency(0)
        q = con.execute("""INSERT INTO queue (member_id, kind, staff_id, automation_ids, headline, detail, draft, trigger,
                           status, due_date, created_at, urgency, urgency_level, urgency_reason, summary)
                           VALUES (?, 'REMINDER', ?, '[]', ?, ?, '', ?, 'open', ?, ?, ?, ?, ?, ?)""",
                        (it["member_id"], staff_id, f"Check in with {first} again",
                         f"Two weeks since your last contact on {today.isoformat()}: \"{note.strip()}\"", it["trigger"],
                         due.isoformat(), now_iso(), score, lvl, why, W.reminder_summary(first, today, note.strip())))
        r = con.execute("INSERT INTO reminders (member_id, staff_id, due_date, reason, from_contact_id, queue_item_id, status, created_at) VALUES (?,?,?,?,?,?, 'scheduled', ?)",
                        (it["member_id"], staff_id, due.isoformat(), "14-day care follow-up", cur.lastrowid, q.lastrowid, now_iso()))
        audit(con, actor=AGENT, actor_type="system", event="reminder_created", member_id=it["member_id"],
              action_taken=f"Follow-up reminder for {due.isoformat()}", routed_to=_staff_label(staff, staff_id),
              details={"reminder_id": r.lastrowid, "queue_item_id": q.lastrowid}, sim_date=today.isoformat())
        out["reminder"] = {"reminder_id": r.lastrowid, "due_date": due.isoformat()}
    else:
        audit(con, actor=staff_id, actor_type="human", event="care_closed", member_id=it["member_id"],
              action_taken="Care closed; no further reminder", reason=note.strip(), sim_date=today.isoformat())
    con.commit()
    return out


def approve_thank(con, item_id: int, staff_id: str, draft: str):
    _require_staff(con, staff_id)
    it = _item(con, item_id)
    if it["kind"] != "THANK":
        raise HumanActionError("only THANK items are approved")
    body = (draft or "").strip()
    if not body:
        raise HumanActionError("the thank-you is empty")
    if (m := ASK_LANGUAGE.search(body)):
        raise HumanActionError(f"a thank-you cannot contain an ask (found: \"{m.group(0)}\")")
    today = sim_date(con).isoformat()
    ids = json.loads(it["automation_ids"])
    con.execute(f"UPDATE decisions SET send_status='replaced_sent', draft=? WHERE automation_id IN ({','.join('?' * len(ids))})", [body, *ids])
    con.execute("UPDATE queue SET status='done', resolved_at=?, resolved_by=?, resolution='approved', draft=? WHERE item_id=?",
                (today, staff_id, body, item_id))
    audit(con, actor=staff_id, actor_type="human", event="thank_you_approved", member_id=it["member_id"],
          automation_id=",".join(ids), action_taken="Thank-you sent (mock) in place of the scheduled ask", decision="THANK",
          reason=body, sim_date=today)
    con.commit()
    return {"ok": True}


def resolve_review(con, item_id: int, staff_id: str, resolution: str, note: str):
    """REVIEW items, or a THANK item a human dismisses. resolution: keep_hold | escalate_care | release | dismiss"""
    _require_staff(con, staff_id)
    it = _item(con, item_id)
    if not note or len(note.strip()) < 3:
        raise HumanActionError("a short note is required")
    today = sim_date(con).isoformat()
    staff = staff_map(con)
    ids = json.loads(it["automation_ids"])
    if resolution == "release":
        if it["kind"] != "REVIEW":
            raise HumanActionError("only REVIEW holds can be released")
        decs = [dict(r) for r in con.execute(f"SELECT * FROM decisions WHERE automation_id IN ({','.join('?' * len(ids))})", ids)]
        hard = [d["guardrail_trigger"] for d in decs if d["guardrail_trigger"] in HARD_TRIGGERS]
        if hard:
            raise HumanActionError(f"hold cannot be released: {', '.join(sorted(set(hard)))} is a hard constraint")
        bundle = build_bundle(con, it["member_id"])
        m, s = bundle["member"], bundle["signals"]
        for a in bundle["scheduled_automation"]:
            if a["automation_id"] in ids:
                if a["is_ask"] == "Yes" and (s.get("is_minor") == "Yes" or (a["ask_category"] == "giving" and s.get("appeals_opt_in") == "No")):
                    raise HumanActionError("hold cannot be released: minor or opted out")
                if not permitted_channel(m, a["channel"]):
                    raise HumanActionError("hold cannot be released: no opted-in channel")
        con.execute(f"UPDATE decisions SET send_status='released_sent' WHERE automation_id IN ({','.join('?' * len(ids))})", ids)
        action = "Released by a person; sent (mock)"
    elif resolution == "escalate_care":
        bundle = build_bundle(con, it["member_id"])
        cands = bundle["relationship_candidates"]
        owner = cands[0]["staff_id"] if cands else "ST02"
        score, lvl, why = U.escalation_urgency()
        con.execute("""INSERT INTO queue (member_id, kind, staff_id, automation_ids, headline, detail, draft, trigger,
                       status, due_date, created_at, urgency, urgency_level, urgency_reason, summary)
                       VALUES (?, 'CARE', ?, ?, ?, ?, '', 'HUMAN_ESCALATION', 'open', ?, ?, ?, ?, ?, ?)""",
                    (it["member_id"], owner, it["automation_ids"], f"{bundle['member']['first_name']} may need you today",
                     f"{_staff_label(staff, staff_id)} read the request and asked for a personal follow-up: \"{note.strip()}\"",
                     today, now_iso(), score, lvl, why,
                     W.escalation_summary(bundle["member"]["first_name"], staff[staff_id]["name"], note.strip())))
        action = f"Escalated to CARE; routed to {_staff_label(staff, owner)}"
    elif resolution in ("keep_hold", "dismiss"):
        action = "Hold kept" if resolution == "keep_hold" else "Dismissed; original message stays cancelled"
    else:
        raise HumanActionError("resolution must be keep_hold, escalate_care, release or dismiss")
    con.execute("UPDATE queue SET status=?, resolved_at=?, resolved_by=?, resolution=?, note=? WHERE item_id=?",
                ("dismissed" if resolution == "dismiss" else "done", today, staff_id, resolution, note.strip(), item_id))
    audit(con, actor=staff_id, actor_type="human", event=f"review_{resolution}", member_id=it["member_id"],
          automation_id=",".join(ids), action_taken=action, reason=note.strip(), sim_date=today)
    con.commit()
    return {"ok": True, "action": action}


def reassign(con, item_id: int, actor_id: str, to_staff_id: str, note: str = ""):
    """Hand a card to someone else. Allowed for the current assignee or a care lead (Care Pastor / Senior Pastor).
    The card keeps its history; drafts are re-signed for the new person."""
    _require_staff(con, actor_id)
    _require_staff(con, to_staff_id)
    it = _item(con, item_id)
    staff = staff_map(con)
    if to_staff_id == it["staff_id"]:
        raise HumanActionError("that person already has this card")
    if actor_id != it["staff_id"] and staff[actor_id]["role"] not in CARE_LEAD_ROLES:
        raise HumanActionError("only the person it is assigned to, or a care lead, can hand it over")
    if it["kind"] == "REVIEW" and staff[to_staff_id]["role"] not in CARE_LEAD_ROLES:
        raise HumanActionError("prayer-request reviews can only go to the Care Pastor or Senior Pastor")
    old_first = staff[it["staff_id"]]["name"].split(" ")[0] if it["staff_id"] in staff else ""
    new_first = staff[to_staff_id]["name"].split(" ")[0]
    draft = it["draft"] or ""
    if old_first:
        draft = draft.replace(f"PRIVATE BRIEF for {old_first}.", f"PRIVATE BRIEF for {new_first}.").replace(f"\n— {old_first}", f"\n— {new_first}")
    today = sim_date(con).isoformat()
    why = note.strip() or "Handed over to share the load"
    detail = it["detail"] + f" Handed over by {staff[actor_id]['name']} on {today}: \"{why}\""
    con.execute("UPDATE queue SET staff_id=?, reassigned_from=?, draft=?, detail=? WHERE item_id=?",
                (to_staff_id, it["staff_id"], draft, detail, item_id))
    audit(con, actor=actor_id, actor_type="human", event="reassigned", member_id=it["member_id"],
          action_taken=f"{it['kind']} card handed from {_staff_label(staff, it['staff_id'])} to {_staff_label(staff, to_staff_id)}",
          reason=why, routed_to=_staff_label(staff, to_staff_id),
          details={"queue_item_id": item_id, "from": it["staff_id"], "to": to_staff_id}, sim_date=today)
    con.commit()
    return {"ok": True, "to": _staff_label(staff, to_staff_id)}


def advance_clock(con, days: int):
    if not 0 < days <= 60:
        raise HumanActionError("days must be 1..60")
    old = sim_date(con)
    new = old + timedelta(days=days)
    set_sim_date(con, new)
    con.execute("UPDATE reminders SET status='due' WHERE status='scheduled' AND due_date<=?", (new.isoformat(),))
    audit(con, actor="demo", actor_type="system", event="clock_advanced", action_taken=f"{old} -> {new}", sim_date=new.isoformat())
    con.commit()
    return {"sim_date": new.isoformat()}

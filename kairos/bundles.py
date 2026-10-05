"""Builds a member bundle from SQLite in the same shape as test_cases.json `input`."""
from datetime import date, timedelta
from .config import AS_OF


def _typed(v):
    if v is None or v == "":
        return None
    for f in (int, float):
        try:
            return f(v)
        except ValueError:
            pass
    return v


def _rows(con, sql, *args):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def build_bundle(con, member_id: str, as_of: date = AS_OF) -> dict:
    m = _rows(con, "SELECT * FROM members WHERE member_id=?", member_id)[0]
    sig = {k: _typed(v) for k, v in _rows(con, "SELECT * FROM member_signal_snapshot WHERE member_id=?", member_id)[0].items()}
    for k in ("milestones_last_14d",):
        sig[k] = sig.get(k) or ""
    for k in ("member_id", "attendance_trend", "giving_status", "volunteer_status", "last_prayer_consent_for_ai",
              "appeals_opt_in", "email_opt_in", "sms_opt_in", "is_minor", "as_of", "last_gift_date", "last_ask_date"):
        if sig.get(k) is not None:
            sig[k] = str(sig[k])
    since16 = (as_of - timedelta(weeks=16)).isoformat()
    since90 = (as_of - timedelta(days=90)).isoformat()
    return {
        "member": m,
        "signals": sig,
        "attendance_last_16w": [r["service_date"] for r in _rows(con, "SELECT service_date FROM attendance WHERE member_id=? AND service_date>? ORDER BY service_date", member_id, since16)],
        "giving": {
            "plan": _rows(con, "SELECT * FROM recurring_plans WHERE member_id=?", member_id),
            "recent_gifts": _rows(con, "SELECT * FROM giving WHERE member_id=? ORDER BY gift_date DESC LIMIT 6", member_id),
        },
        "volunteering": _rows(con, "SELECT * FROM volunteer_roles WHERE member_id=?", member_id),
        "prayer_requests": [{**p, "request_text": p["request_text"] if p["consent_for_ai_read"] == "Yes"
                             else "[RESTRICTED: request text not shared with Kairos; member did not consent]"}
                            for p in _rows(con, "SELECT request_id, submitted_at, request_text, consent_for_ai_read, status, visibility FROM prayer_requests WHERE member_id=? ORDER BY submitted_at", member_id)],
        "pastoral_notes": _rows(con, "SELECT note_id, note_date, author_staff_id, note_type, note_text FROM pastoral_notes WHERE member_id=? ORDER BY note_date", member_id),
        "communications_last_90d": _rows(con, "SELECT sent_at, workflow_name, ask_category, is_ask FROM communications_log WHERE member_id=? AND sent_at>? ORDER BY sent_at", member_id, since90),
        "scheduled_automation": _rows(con, "SELECT * FROM scheduled_automation WHERE member_id=? ORDER BY scheduled_send_at", member_id),
        "relationship_candidates": [{"staff_id": r["staff_id"], "role": r["relationship_role"], "strength_pct": int(r["strength_pct"])}
                                    for r in _rows(con, "SELECT * FROM relationship_strength WHERE member_id=? ORDER BY CAST(strength_pct AS INT) DESC", member_id)],
    }

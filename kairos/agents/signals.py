"""SignalAgent: turns a raw member bundle (test-case `input` shape) into normalized facts.
Deterministic. Never interprets free text; it only dates it and records consent."""
from datetime import date
from ..config import AS_OF
from ..schemas import TextItem


def _d(s) -> date | None:
    if not s:
        return None
    return date.fromisoformat(str(s)[:10])


def days_ago(s, as_of: date = AS_OF) -> int | None:
    d = _d(s)
    return None if d is None else (as_of - d).days


class SignalAgent:
    name = "SignalAgent"

    def run(self, bundle: dict, as_of: date = AS_OF) -> dict:
        items: list[TextItem] = []
        for p in bundle.get("prayer_requests", []):
            consent = p.get("consent_for_ai_read") == "Yes"
            items.append(TextItem(
                kind="prayer", item_id=p.get("request_id", ""), on=str(p["submitted_at"])[:10],
                days_ago=days_ago(p["submitted_at"], as_of),
                text=p["request_text"] if consent else None,  # never even hand restricted text to downstream agents
                consent=consent, status=p.get("status", "")))
        for n in bundle.get("pastoral_notes", []):
            items.append(TextItem(
                kind="note", item_id=n.get("note_id", ""), on=str(n["note_date"])[:10],
                days_ago=days_ago(n["note_date"], as_of), text=n.get("note_text", ""),
                note_type=n.get("note_type", "")))
        s = bundle["signals"]
        m = bundle["member"]
        facts = {
            "member": m,
            "signals": s,
            "items": items,
            "relationship_candidates": bundle.get("relationship_candidates", []),
            "automations": bundle.get("scheduled_automation", []),
            "is_visitor": m.get("membership_status") == "Visitor",
        }
        return facts

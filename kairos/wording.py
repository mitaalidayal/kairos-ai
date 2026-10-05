"""Plain-language card text for the Human Attention Queue. The engine's `reason` stays in the audit log;
cards say what is going on, in the words a pastor or volunteer would use. Never quotes prayer text."""
from datetime import date, timedelta
from .config import AS_OF

NEED = {"serious_illness": "a serious health concern", "grief": "a recent loss", "mental_health": "a hard time emotionally",
        "financial_hardship": "money pressures", "homelessness_risk": "possibly losing their home",
        "job_loss": "losing a job", "family_crisis": "a family crisis"}


def day(d) -> str:
    """'2026-09-30' or date -> 'Sep 30'."""
    if not d:
        return ""
    d = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
    return f"{d:%b} {d.day}"


def _evidence_date(d, as_of=AS_OF):
    return as_of - timedelta(days=d.evidence_days_ago) if d.evidence_days_ago is not None else None


def _years(code: str) -> str:
    code = code or ""
    n, unit = (int(code[:-1]), code[-1]) if code[:-1].isdigit() else (0, "")
    years = n if unit == "y" else (n // 12 if unit == "m" and n % 12 == 0 else None)
    if years is None:
        return f"{n} months" if n else "a while"
    return "a year" if years == 1 else f"{years} years"


def care_summary(d, bundle) -> str:
    first = bundle["member"]["first_name"]
    s = bundle["signals"]
    if d.rule == "R4":
        return (f"{first} has quietly stepped back: {s.get('attended_prior_8w')} of 8 Sundays before, {s.get('attended_last_8w')} of the last 8, "
                f"stopped volunteering and paused their monthly gift. Nothing on file explains it.")
    need = NEED.get(d.sacred_type, "something hard")
    when = day(_evidence_date(d))
    if d.evidence_kind == "note":
        return f"A pastoral note from {when} says {first} is facing {need}."
    return f"{first} shared a prayer request on {when} about {need}."


def review_summary(d, bundle) -> str:
    first = bundle["member"]["first_name"]
    when = day(_evidence_date(d))
    if d.guardrail_trigger == "CONSENT_RESTRICTED":
        return (f"{first} sent a prayer request on {when} and chose not to let Kairos read it. "
                f"Please read it in the care system before any message goes out.")
    if d.guardrail_trigger == "AMBIGUOUS_SENSITIVE":
        return (f"{first}'s prayer request on {when} might be about something hard, but it isn't clear. "
                f"Messages are paused until someone reads it.")
    return f"Something in a recent note or prayer request from {first} needs a person to look at it before any message goes out."


def thank_summary(d, bundle) -> str:
    first = bundle["member"]["first_name"]
    ms = (bundle["signals"].get("milestones_last_14d") or "").strip()
    team = next((v["team"] for v in bundle.get("volunteering", []) if v.get("team")), "")
    note = lambda t: next((n["note_text"] for n in reversed(bundle.get("pastoral_notes", [])) if n.get("note_type") == t), "")
    if ms.startswith("volunteer_anniversary"):
        where = (team if team.lower().endswith("team") else f"{team} team") if team else "volunteer team"
        return f"{first} has served on the {where} for {_years(ms.rsplit('_', 1)[-1])}."
    if ms.startswith("recurring_gift_anniversary"):
        return f"{first} has been giving regularly for {_years(ms.rsplit('_', 1)[-1])}."
    if ms == "first_gift":
        return f"{first} gave for the first time."
    if ms == "major_gift":
        return f"{first} made a generous gift."
    if ms == "spiritual_milestone":
        return f"A big step for {first}: {note('Milestone') or 'a spiritual milestone'}"
    if ms == "impact_update":
        return f"Something {first} gave to just made a difference: {note('Impact update')}"
    when = day(_evidence_date(d))
    return f"{first} shared good news in a prayer request{' on ' + when if when else ''}."


def reminder_summary(first: str, contact_day, note: str) -> str:
    return f"Last check-in with {first} was {day(contact_day)}: “{note}”. Time to see how they're doing."


def escalation_summary(first: str, staff_name: str, note: str) -> str:
    return f"{staff_name} read {first}'s prayer request and asked for a personal follow-up: “{note}”"

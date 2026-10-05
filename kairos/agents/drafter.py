"""DraftAgent: prepares text for a HUMAN to review. It never sends anything.
- THANK: a short personal thank-you (no ask), first name only, signed by the routed person.
- CARE: a private brief for the routed staff member (what Kairos noticed, how to approach). Never quotes the
  prayer text: the routed person may not be on the care team, so they are pointed to the care record instead.
- ASK + CHANGE (resolved history): a softened opener in front of the scheduled draft.
Template-based so it is deterministic offline; the Guardrail re-checks the thank-you for ask language."""
from ..schemas import Decision

MILESTONE_LINES = {
    "volunteer_anniversary": "it's been {n} of serving on the team, and we noticed. Thank you for showing up week after week.",
    "recurring_gift_anniversary": "it's been {n} since you started giving faithfully. Thank you for being part of what God is doing here.",
    "first_gift": "we saw your first gift come in and just wanted to say thank you. It means a lot.",
    "major_gift": "thank you for your recent generosity. It is making a real difference.",
    "spiritual_milestone": "we are so glad to celebrate this step with you.",
    "impact_update": "you were part of this: {impact} Thank you.",
    "praise": "we heard your good news and are celebrating with you. Thank you for letting us pray alongside you.",
}
TYPE_WORDS = {"serious_illness": "a serious health concern", "grief": "a loss", "mental_health": "a hard season emotionally",
              "financial_hardship": "financial strain", "homelessness_risk": "a housing crisis", "job_loss": "a job loss",
              "family_crisis": "a family crisis"}


def _duration(code: str) -> str:
    """'10y' -> '10 years', '12m' -> 'a year', '24m' -> '2 years', '6m' -> '6 months'."""
    if not code or not code[:-1].isdigit():
        return ""
    n, unit = int(code[:-1]), code[-1]
    years = n if unit == "y" else (n // 12 if n % 12 == 0 else None)
    if years is None:
        return f"{n} months"
    return "a year" if years == 1 else f"{years} years"


def _milestone(ms: str):
    ms = (ms or "").strip()
    for key in MILESTONE_LINES:
        if ms.startswith(key):
            return key, _duration(ms[len(key):].strip("_"))
    return ("praise", "") if not ms else (ms, "")


class DraftAgent:
    name = "DraftAgent"

    def __init__(self, staff: dict | None = None):
        self.staff = staff or {}

    def run(self, facts: dict, auto: dict, d: Decision) -> Decision:
        first = facts["member"].get("first_name", "friend")
        sender = self.staff.get(d.human_staff_id, {}).get("name", "").split(" ")[0] or "Your church family"
        if d.decision == "THANK":
            key, n = _milestone(facts["signals"].get("milestones_last_14d"))
            impact = next((it.text for it in facts["items"] if it.note_type == "Impact update" and it.text), "")
            line = MILESTONE_LINES.get(key, MILESTONE_LINES["praise"]).format(n=n or "a while", impact=impact)
            d.draft = f"Hi {first},\n\nJust a quick note: {line}\n\nNo agenda, just grateful for you.\n— {sender}"
        elif d.decision == "CARE":
            src = "prayer request" if d.rule == "R1" else "attendance, giving and volunteering pattern"
            what = TYPE_WORDS.get(d.sacred_type, "something going on") if d.rule == "R1" else "a sudden, unexplained step back"
            d.draft = (f"PRIVATE BRIEF for {sender}. Do not forward.\n"
                       f"Kairos noticed {what} from a recent {src} for {first}.\n"
                       f"All automated asks and nudges to {first} are paused.\n"
                       f"Suggested: a personal call or visit. Listen first. Do not mention giving or volunteering.\n"
                       + ("The full request is in the care record (care team only).\n" if d.rule == "R1" else "")
                       + "After you connect, log a short note. Kairos will remind you to check in again in 14 days.")
        elif d.decision == "ASK" and d.automation_action == "CHANGE":
            d.draft = (f"Hi {first}, we have been thinking of you and your family and are grateful you're with us. "
                       f"{auto.get('draft_summary', '')}")
        if d.draft:
            d.trace.append({"agent": self.name, "drafted": d.decision})
        return d

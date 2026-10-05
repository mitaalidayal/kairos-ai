"""Keyword classifier. Used (a) as the offline fallback for the Sacred Moment Detector and
(b) by the Guardrail as an independent second opinion. Unknown text is labelled "ambiguous" (fail closed)."""
import re
from ..schemas import TextLabel

SACRED = {
    "serious_illness": ["cancer", "chemo", "tumor", "diagnos", "surgery", "icu", "intensive care", "hospice",
                        "heart attack", "stroke", "hospital", "treatment", "heart condition"],
    "grief": ["passed away", "died", "funeral", "lost our baby", "grief", "miscarriage"],
    "mental_health": ["depress", "anxiety", "overwhelmed", "feel very alone", "withdrawn", "feels alone",
                      "not been sleeping", "drowning", "suicid", "panic attack"],
    "homelessness_risk": ["evict", "living in our car", "staying in our car", "motel", "nowhere to stay",
                          "nowhere to go", "losing our apartment", "shelter"],
    "financial_hardship": ["behind on rent", "no money for groceries", "electric bill", "running out of money",
                           "can't pay", "cannot pay"],
    "job_loss": ["laid off", "lost my job", "lost his job", "lost her job", "fired"],
    "family_crisis": ["separating", "ran away", "divorce", "custody"],
}
# Order matters when several types match: the more specific or acute type wins.
TYPE_PRIORITY = ["homelessness_risk", "grief", "mental_health", "serious_illness", "job_loss", "financial_hardship", "family_crisis"]

PRAISE = ["praise report", "welcomed our baby", "got the job", "came home from the hospital", "cancer-free",
          "answered prayer", "recovering well", "thank you for praying"]
AMBIGUOUS = ["appointment", "tests coming up", "pray for my family this week", "it has been a lot", "results"]
OTHER_PERSON = ["coworker", "co-worker", "a close friend", "my friend", "neighbor", "neighbour", "a friend"]
RESOLVED = ["follow-up call completed", "care visit complete", "doing much better", "things are stable"]
ABSENCE = ["trip abroad", "out of town", "overseas", "travelling", "traveling", "away until", "on vacation", "away for"]
ROUTINE = ["youth group", "our church", "mission trip", "doing well", "catching up", "graduation",
           "school year", "small group", "new study", "retreat", "vbs"]

INJECTION = re.compile(
    r"(ignore (all )?(previous|prior|above) instructions|^\s*system\s*:|\bsystem prompt\b|"
    r"classify (me|this|them) as|mark (this|me|the) (member|person)? ?as|send the .* immediately|"
    r"you are now|disregard .*instructions)", re.I | re.M)


def has_injection(text: str) -> bool:
    return bool(INJECTION.search(text or ""))


def _sacred_type(t: str):
    hits = [k for k in TYPE_PRIORITY if any(w in t for w in SACRED[k])]
    return hits[0] if hits else None


def classify(text: str, kind: str = "prayer", note_type: str = "") -> TextLabel:
    t = (text or "").lower()
    inj = has_injection(t)
    if kind == "note":
        if note_type in ("Milestone", "Impact update"):
            return TextLabel("praise", injection_attempt=inj)
        if any(k in t for k in RESOLVED):
            return TextLabel("resolved_followup", injection_attempt=inj)
        if any(k in t for k in ABSENCE):
            return TextLabel("absence", injection_attempt=inj)
    if any(k in t for k in PRAISE):
        return TextLabel("praise", injection_attempt=inj)
    st = _sacred_type(t)
    if st:
        # Someone else's crisis is sacred-adjacent, except grief: losing a friend is the member's own grief.
        if any(k in t for k in OTHER_PERSON) and st != "grief":
            return TextLabel("other_person", injection_attempt=inj)
        return TextLabel("sacred", st, injection_attempt=inj)
    if any(k in t for k in AMBIGUOUS):
        return TextLabel("ambiguous", injection_attempt=inj)
    if any(k in t for k in ROUTINE):
        return TextLabel("routine", injection_attempt=inj)
    return TextLabel("ambiguous", injection_attempt=inj)  # unknown -> fail closed


def sacred_keyword_hit(text: str) -> bool:
    """Used by the Guardrail: any sacred keyword at all, regardless of context."""
    t = (text or "").lower()
    return any(w in t for ws in SACRED.values() for w in ws)


def ambiguous_keyword_hit(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in AMBIGUOUS)


def absence_keyword_hit(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in ABSENCE)

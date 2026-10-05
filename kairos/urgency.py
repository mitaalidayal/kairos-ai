"""Urgency for CARE-type queue items, so an overloaded person reaches the right people first.
Deterministic and explainable: base weight by kind of need + a recency bonus. Not a model, not a prediction.

  score >= 6  -> "urgent"     score 4-5 -> "high"     else -> "normal"
"""

# How acute each kind of need usually is when it first surfaces.
TYPE_WEIGHT = {
    "homelessness_risk": 5,   # may not have a safe place to sleep tonight
    "grief": 4,               # the first days after a death matter most
    "mental_health": 4,
    "family_crisis": 4,       # e.g. a runaway child
    "serious_illness": 3,
    "financial_hardship": 3,
    "job_loss": 2,
}
PRETTY = {"homelessness_risk": "possible loss of housing", "grief": "a recent loss", "mental_health": "mental health",
          "family_crisis": "a family crisis", "serious_illness": "serious illness", "financial_hardship": "financial strain",
          "job_loss": "job loss"}


def level(score: int) -> str:
    return "urgent" if score >= 6 else "high" if score >= 4 else "normal"


def care_urgency(sacred_type: str | None, days_ago: int | None, rule: str = "R1"):
    """Returns (score, level, reason) for a CARE item."""
    if rule == "R4" or not sacred_type:
        score, why = 1, "unexplained step back, no crisis on file"
    else:
        score, why = TYPE_WEIGHT.get(sacred_type, 3), PRETTY.get(sacred_type, sacred_type)
        if days_ago is not None:
            if days_ago <= 3:
                score += 2; why += f", shared {days_ago} day{'s' if days_ago != 1 else ''} ago"
            elif days_ago <= 7:
                score += 1; why += f", shared {days_ago} days ago"
            else:
                why += f", shared {days_ago} days ago"
    return score, level(score), why


def escalation_urgency():
    return 4, level(4), "a staff member read the request and asked for follow-up"


def reminder_urgency(overdue_days: int = 0):
    score = 3 + min(overdue_days // 7, 3)
    return score, level(score), "two-week follow-up" + (f", {overdue_days} days overdue" if overdue_days > 0 else "")

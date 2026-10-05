"""Enums and the output contract. Anything outside these sets is rejected."""
from dataclasses import dataclass, field, asdict
from typing import Optional

DECISIONS = ("ASK", "CARE", "THANK", "WAIT")
ACTIONS = ("CONTINUE", "CHANGE", "BLOCK")
SACRED_TYPES = ("serious_illness", "grief", "mental_health", "financial_hardship",
                "homelessness_risk", "job_loss", "family_crisis")
TEXT_CATEGORIES = ("sacred", "ambiguous", "praise", "other_person", "resolved_followup", "absence", "routine")

# Hard constraints: a human may NOT release these holds from the dashboard.
NON_RELEASABLE_TRIGGERS = {"MINOR", "OPT_OUT", "CONSENT_RESTRICTED", "SACRED_WINDOW", "SYSTEM_ERROR"}

# Messages that are not personal outreach. They pass through untouched unless a member-level flag (R1-R4) applies.
ROUTINE_TYPES = ("newsletter", "birthday")


@dataclass
class TextLabel:
    category: str
    sacred_type: Optional[str] = None
    injection_attempt: bool = False
    source: str = "keyword"          # "llm" | "keyword" | "cache" | "skipped"

    def __post_init__(self):
        if self.category not in TEXT_CATEGORIES:
            raise ValueError(f"bad category {self.category!r}")
        if self.category == "sacred" and self.sacred_type not in SACRED_TYPES:
            raise ValueError(f"bad sacred_type {self.sacred_type!r}")
        if self.category != "sacred":
            self.sacred_type = None if self.sacred_type not in SACRED_TYPES else self.sacred_type


@dataclass
class TextItem:
    """One prayer request or pastoral note, as seen by the agents."""
    kind: str                 # "prayer" | "note"
    item_id: str
    on: str                   # ISO date
    days_ago: int
    text: Optional[str]       # None when consent_for_ai_read = No (never read)
    consent: bool = True
    status: str = ""          # prayer: Open/Resolved
    note_type: str = ""
    label: Optional[TextLabel] = None


@dataclass
class Decision:
    automation_id: str
    member_id: str
    decision: str
    automation_action: str
    sacred_detected: str = "No"           # Yes | No | Uncertain
    sacred_type: Optional[str] = None
    guardrail_result: str = "NA"          # PASS | BLOCK | NA
    guardrail_trigger: str = ""
    requires_human_review: str = "No"
    human_staff_id: str = ""
    human_role: str = ""
    human_reason: str = ""
    channel: str = ""
    follow_up_days: Optional[int] = None
    evidence_days_ago: Optional[int] = None   # age of the text that triggered the decision (urgency, card wording)
    evidence_kind: str = ""                    # "prayer" | "note" | ""
    reason: str = ""
    rule: str = ""
    routine: bool = False                 # routine pass-through: never enters the Human Attention Queue
    injection_flag: bool = False
    draft: str = ""
    trace: list = field(default_factory=list)

    def validate(self):
        assert self.decision in DECISIONS, self.decision
        assert self.automation_action in ACTIONS, self.automation_action
        assert self.sacred_detected in ("Yes", "No", "Uncertain")
        assert self.requires_human_review in ("Yes", "No")
        return self

    def contract(self) -> dict:
        """The public output contract from the brief."""
        return {
            "decision": self.decision,
            "automation_action": self.automation_action,
            "sacred_moment": {"detected": self.sacred_detected, "type": self.sacred_type or ""},
            "guardrail": {"result": self.guardrail_result, "trigger": self.guardrail_trigger},
            "requires_human_review": self.requires_human_review,
            "human": {"staff_id": self.human_staff_id, "role": self.human_role},
            "channel": self.channel,
            "follow_up_days": self.follow_up_days,
            "reason": self.reason,
        }

    def to_dict(self):
        return asdict(self)

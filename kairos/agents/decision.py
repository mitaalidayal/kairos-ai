"""DecisionAgent: deterministic priority rules R1-R8 (+R10 modifier). First match wins.
Consumes SignalAgent facts whose text items have already been labelled by the Sacred Moment Detector."""
from .. import config as C
from ..schemas import Decision, ROUTINE_TYPES

PRETTY = {"serious_illness": "serious illness", "grief": "grief", "mental_health": "a mental health struggle",
          "financial_hardship": "financial hardship", "homelessness_risk": "possible loss of housing",
          "job_loss": "job loss", "family_crisis": "a family crisis"}


def _num(x, default=None):
    try:
        return default if x is None or x == "" else float(x)
    except (TypeError, ValueError):
        return default


def permitted_channel(m, preferred):
    """Product rule: consent is "may we contact this person at all". If they opted in to email OR text, send on
    their preferred channel; if they opted in to neither, send nothing (None -> OPT_OUT hold)."""
    consented = m.get("email_opt_in") == "Yes" or m.get("sms_opt_in") == "Yes"
    if not consented:
        return None
    return preferred if preferred in ("email", "text") else ("email" if m.get("email_opt_in") == "Yes" else "text")


def _src(it):
    return "prayer request" if it.kind == "prayer" else "pastoral note"


class DecisionAgent:
    name = "DecisionAgent"

    def _resolved(self, item, items):
        """A sacred item is resolved if the prayer is marked Resolved, or a later follow-up note says so."""
        if item.kind == "prayer" and item.status == "Resolved":
            return True
        return any(o.label and o.label.category == "resolved_followup" and o.on >= item.on for o in items)

    def run(self, facts: dict, auto: dict) -> Decision:
        s, m, items = facts["signals"], facts["member"], facts["items"]
        is_ask = auto.get("is_ask") == "Yes"
        mtype = auto.get("message_type", "")
        cat = auto.get("ask_category", "none")
        routine = mtype in ROUTINE_TYPES
        d = Decision(automation_id=auto["automation_id"], member_id=m["member_id"], decision="WAIT", automation_action="BLOCK")
        lab = lambda it: it.label.category if it.label else None
        within = lambda it, n: it.days_ago is not None and 0 <= it.days_ago <= n
        d.injection_flag = any(it.label and it.label.injection_attempt for it in items)

        # R1 sacred, unresolved, within 45 days (prayer text or pastoral notes) -> CARE, block ALL outreach
        sacred = [it for it in items if lab(it) == "sacred" and within(it, C.SACRED_WINDOW_DAYS) and not self._resolved(it, items)]
        if sacred:
            it = min(sacred, key=lambda x: x.days_ago)
            d.decision, d.automation_action, d.rule = "CARE", "BLOCK", "R1"
            d.sacred_detected, d.sacred_type = "Yes", it.label.sacred_type
            d.evidence_days_ago, d.evidence_kind = it.days_ago, it.kind
            d.guardrail_result, d.guardrail_trigger = "BLOCK", "SACRED_WINDOW"
            d.requires_human_review, d.follow_up_days = "Yes", C.CARE_FOLLOW_UP_DAYS
            d.channel = "Personal call or visit"
            d.reason = (f"A {_src(it)} from {it.days_ago} days ago points to {PRETTY[it.label.sacred_type]}. "
                        f"The scheduled '{auto.get('workflow_name')}' message would talk past it, so it is blocked and a person is asked to reach out.")
            return d

        # Routine broadcasts (newsletter, birthday) pass through untouched unless the member is in a CARE moment
        # (R1 above, R4 here). Ambiguous or restricted prayer holds personal outreach, not a church-wide newsletter.
        if routine:
            if self._dropoff(s, items):
                return self._dropoff_care(d, s)
            d.decision, d.automation_action, d.rule, d.routine = "ASK", "CONTINUE", "ROUTINE", True
            d.guardrail_result, d.guardrail_trigger = "PASS", "ROUTINE_PASSTHROUGH"
            d.channel = permitted_channel(m, auto.get("channel") or m.get("preferred_channel")) or ""
            d.reason = f"Routine '{auto.get('workflow_name')}' with no flags on this person. Sent unchanged."
            return d

        # R2 consent restricted prayer within 21 days -> WAIT, never read or infer
        restricted = [it for it in items if it.kind == "prayer" and not it.consent and within(it, C.UNCERTAIN_TEXT_DAYS)]
        if restricted:
            d.evidence_days_ago, d.evidence_kind = min(x.days_ago for x in restricted), "prayer"
            return self._wait(d, "R2", "CONSENT_RESTRICTED", review=True, sacred="Uncertain",
                              reason="A recent prayer request was shared without consent for AI reading. Kairos did not read it. A staff member should read it before anything is sent.")

        # R3 ambiguous sensitive wording within 21 days
        amb = [it for it in items if lab(it) == "ambiguous" and within(it, C.UNCERTAIN_TEXT_DAYS)]
        if amb:
            d.evidence_days_ago, d.evidence_kind = amb[0].days_ago, amb[0].kind
            return self._wait(d, "R3", "AMBIGUOUS_SENSITIVE", review=True, sacred="Uncertain",
                              reason=f"A recent {_src(amb[0])} hints at something sensitive but is not clear. Holding the message until a person reads it.")

        # R4 multi-signal drop-off for a long-tenured member with no context anywhere
        if self._dropoff(s, items):
            return self._dropoff_care(d, s)

        # R5 prayer for someone else's crisis -> short hold on asks
        if is_ask and any(lab(it) == "other_person" and within(it, C.SACRED_ADJACENT_HOLD_DAYS) for it in items):
            return self._wait(d, "R5", "SACRED_ADJACENT", review=False,
                              reason="They recently asked prayer for someone close who is in crisis. Holding asks for about two weeks.")

        # R6 milestone in last 14 days, or praise report
        ms = (s.get("milestones_last_14d") or "").strip()
        praise = [it for it in items if lab(it) == "praise" and within(it, C.MILESTONE_DAYS)]
        if ms or praise:
            d.decision, d.automation_action, d.rule = "THANK", "CHANGE", "R6"
            d.requires_human_review, d.channel = "Yes", "Handwritten note or personal call"
            what = ms.replace("_", " ") if ms else f"a praise report in a recent {_src(praise[0])}"
            if praise and not ms:
                d.evidence_days_ago, d.evidence_kind = praise[0].days_ago, praise[0].kind
            d.reason = f"Milestone: {what}. Replace the scheduled '{auto.get('workflow_name')}' with a personal thank-you that has no ask."
            return d

        # R7 guardrail holds
        hold = self._r7(facts, auto, is_ask, cat, mtype)
        if hold:
            trig, why = hold
            return self._wait(d, "R7", trig, review=False, reason=why)

        # R8 healthy engagement -> ASK
        att = _num(s.get("attended_last_8w"), 0)
        newer = facts["is_visitor"] or _num(s.get("tenure_months"), 0) <= C.NEWER_ATTENDER_MONTHS
        if (not is_ask) or att >= C.HEALTHY_ATTENDANCE_OF_8 or (cat == "participation" and newer):
            d.decision, d.automation_action, d.rule = "ASK", "CONTINUE", "R8"
            d.guardrail_result = "PASS"
            d.channel = permitted_channel(m, auto.get("channel") or m.get("preferred_channel"))
            d.reason = (f"Healthy engagement ({int(att)} of the last 8 services) and no flags. The '{auto.get('workflow_name')}' can send."
                        if is_ask else f"No flags. The '{auto.get('workflow_name')}' can send.")
            # R10 modifier: past sacred moment resolved > 90 days ago -> softer tone
            res = [it for it in items if it.label and it.label.category == "resolved_followup"]
            if res:
                newest = min(res, key=lambda x: x.days_ago)
                if newest.days_ago > C.RESOLVED_SOFTEN_DAYS:
                    d.automation_action, d.rule = "CHANGE", "R8+R10"
                    d.reason += f" A past care moment was followed up and resolved {newest.days_ago} days ago, so the tone is softened."
                else:
                    return self._wait(d, "R10", "RECENTLY_RESOLVED", review=False,
                                      reason=f"A care moment was resolved only {newest.days_ago} days ago. Too soon to resume asks.")
            return d

        return self._wait(d, "R8", "LOW_ENGAGEMENT", review=False,
                          reason=f"Only {int(att)} of the last 8 services attended. Not enough engagement for this ask, so holding (fail closed).")

    @staticmethod
    def _dropoff(s, items):
        lab = lambda it: it.label.category if it.label else None
        context = any(lab(it) in ("sacred", "ambiguous", "absence", "other_person") for it in items) or any(not it.consent for it in items)
        return (s.get("attendance_trend") == "sharp_down" and s.get("volunteer_status") == "Inactive"
                and "Paused" in str(s.get("giving_status")) and _num(s.get("tenure_months"), 0) >= C.DROPOFF_MIN_TENURE_MONTHS
                and not context)

    @staticmethod
    def _dropoff_care(d, s):
        d.decision, d.automation_action, d.rule = "CARE", "BLOCK", "R4"
        d.guardrail_result, d.guardrail_trigger = "BLOCK", "MULTI_SIGNAL_DROPOFF"
        d.requires_human_review, d.follow_up_days = "Yes", C.CARE_FOLLOW_UP_DAYS
        d.channel = "Personal call or visit"
        d.reason = (f"Attendance fell to {s.get('attended_last_8w')}/8, volunteering went inactive and the recurring gift paused, "
                    f"for someone here {int(_num(s.get('tenure_months'), 0)) // 12}+ years, with no explanation on file. A soft personal check-in, not a retention email.")
        return d

    def _r7(self, facts, auto, is_ask, cat, mtype):
        s, m, items = facts["signals"], facts["member"], facts["items"]
        giving = cat == "giving"
        chan = auto.get("channel") or m.get("preferred_channel")
        if is_ask:
            if s.get("is_minor") == "Yes":
                return "MINOR", "Member is a minor. No asks to minors."
            if giving and s.get("appeals_opt_in") == "No":
                return "OPT_OUT", "Member opted out of giving appeals."
        if not permitted_channel(m, chan):
            return "OPT_OUT", "Member has not opted in to email or text."
        if is_ask:
            if _num(s.get("tenure_months"), 0) < 1 and _num(s.get("attended_last_8w"), 0) == 0:
                return "INSUFFICIENT_DATA", "Brand new with no attendance yet. Not enough history to judge an ask."
            if giving and facts["is_visitor"]:
                return "NEW_VISITOR", "New visitor. No giving asks to visitors."
            if _num(s.get("asks_last_30d"), 0) >= 1:
                return "RECENT_ASK", "Already asked in the last 30 days (max one ask per 30 days)."
            if giving and _num(s.get("days_since_last_one_time_gift"), 9999) <= C.JUST_GAVE_DAYS:
                return "JUST_GAVE", f"Made a one-time gift {int(_num(s.get('days_since_last_one_time_gift')))} days ago."
        dhc = _num(s.get("days_since_human_contact"), 9999)
        if dhc <= C.HUMAN_CONTACT_DAYS:
            return "RECENT_HUMAN_CONTACT", f"A pastor or leader was in personal contact {int(dhc)} days ago. Let that relationship lead."
        if any(it.label and it.label.category == "absence" for it in items if it.days_ago is not None and it.days_ago <= C.SACRED_WINDOW_DAYS):
            return "EXPLAINED_ABSENCE", "A note says they are away. The absence is explained; hold until they are back."
        return None

    @staticmethod
    def _wait(d, rule, trig, review, reason, sacred="No"):
        d.decision, d.automation_action, d.rule = "WAIT", "BLOCK", rule
        d.guardrail_result, d.guardrail_trigger = "BLOCK", trig
        d.requires_human_review, d.sacred_detected = "Yes" if review else "No", sacred
        d.reason = reason
        return d

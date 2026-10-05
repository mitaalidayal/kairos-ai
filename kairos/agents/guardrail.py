"""GuardrailAgent: the last check before anything leaves Kairos. It re-verifies hard constraints from the RAW
bundle (not from other agents' conclusions) and may only DOWNGRADE a decision (ASK/THANK -> WAIT). It never
produces ASK and never unblocks anything."""
import re
from .. import config as C
from ..schemas import Decision
from .keywords import sacred_keyword_hit, ambiguous_keyword_hit, absence_keyword_hit, has_injection
from .decision import permitted_channel

# Ask *intent*, not topic: a first-gift thank-you may say "gift"; it may not ask for one.
ASK_LANGUAGE = re.compile(r"(would you (consider|like to)|consider (giving|a gift|donating|serving)|give (today|now|again)|"
                          r"please (give|donate|consider)|donate|pledge|sign up|restart|increase your|set up a recurring|"
                          r"join us in giving|can you (give|help|serve)|click|https?://|\bgive\b.*\?)", re.I)


class GuardrailAgent:
    name = "GuardrailAgent"

    def run(self, facts: dict, auto: dict, d: Decision) -> Decision:
        checks, s, m = [], facts["signals"], facts["member"]
        is_ask = auto.get("is_ask") == "Yes"
        giving = auto.get("ask_category") == "giving"

        def downgrade(trigger, why, review="Yes", sacred=None):
            prev = (d.decision, d.automation_action)
            d.decision, d.automation_action = "WAIT", "BLOCK"
            d.guardrail_result, d.guardrail_trigger, d.requires_human_review = "BLOCK", trigger, review
            d.channel, d.follow_up_days, d.routine = "", None, False
            d.human_staff_id = d.human_role = d.human_reason = ""
            if sacred:
                d.sacred_detected = sacred
            d.reason = f"Guardrail held this message: {why} (was {prev[0]}/{prev[1]})."
            checks.append({"check": trigger, "result": "DOWNGRADE", "from": prev})

        # 1. Structural consistency of the contract
        valid = {("ASK", "CONTINUE"), ("ASK", "CHANGE"), ("THANK", "CHANGE"), ("CARE", "BLOCK"), ("WAIT", "BLOCK")}
        if (d.decision, d.automation_action) not in valid:
            downgrade("CONTRACT_INVALID", "decision and action did not form a valid pair")

        # 2. Independent second opinion on recent text, using keywords only (not the Detector's labels,
        #    except where the Detector positively explained the text as praise / someone else / resolved).
        recent = [it for it in facts["items"] if it.days_ago is not None and 0 <= it.days_ago <= C.SACRED_WINDOW_DAYS]
        explained = lambda it: (it.kind == "prayer" and it.status == "Resolved") or \
            (it.label and it.label.category in ("resolved_followup", "praise", "other_person", "sacred"))
        kw_sacred = [it for it in recent if it.consent and sacred_keyword_hit(it.text) and not explained(it)]
        kw_ambig = [it for it in recent if it.consent and it.days_ago <= C.UNCERTAIN_TEXT_DAYS
                    and ambiguous_keyword_hit(it.text) and not explained(it)]
        # Escalate even an already-held message if nobody would otherwise look at it.
        quiet = d.decision != "CARE" and not (d.decision == "WAIT" and d.requires_human_review == "Yes")
        if quiet and kw_sacred:
            downgrade("SECOND_OPINION_SACRED", "the independent keyword check found possible sacred language the detector did not flag", sacred="Uncertain")
        elif quiet and d.decision in ("ASK", "THANK") and kw_ambig and not d.routine:
            downgrade("SECOND_OPINION_AMBIGUOUS", "the independent keyword check found possibly sensitive wording", sacred="Uncertain")

        # 3. Anything that would send automatically: re-verify hard constraints from raw data
        if d.decision == "ASK":
            consent_block = any(it.kind == "prayer" and not it.consent and it.days_ago <= C.UNCERTAIN_TEXT_DAYS for it in recent)
            injected = [it for it in recent if it.consent and has_injection(it.text)]
            if consent_block and not d.routine:
                downgrade("CONSENT_RESTRICTED", "a recent prayer request is restricted from AI reading", sacred="Uncertain")
            elif injected:
                downgrade("INJECTION_SUSPECTED", "recent member text contains instruction-like content; a person should look before any ask")
            elif not d.routine and any(it.kind == "note" and absence_keyword_hit(it.text) for it in recent):
                downgrade("EXPLAINED_ABSENCE", "a recent note says they are away", review="No")
            elif is_ask and s.get("is_minor") == "Yes":
                downgrade("MINOR", "member is a minor", review="No")
            elif is_ask and giving and s.get("appeals_opt_in") == "No":
                downgrade("OPT_OUT", "member opted out of appeals", review="No")
            elif not permitted_channel(m, auto.get("channel") or m.get("preferred_channel")):
                downgrade("OPT_OUT", "no channel the member opted in to", review="No")
            elif is_ask and float(s.get("asks_last_30d") or 0) >= 1:
                downgrade("RECENT_ASK", "already asked in the last 30 days", review="No")
            else:
                checks.append({"check": "send_constraints", "result": "PASS"})

        # 4. Sensitive outcomes always need a human; CARE always needs an owner and a follow-up
        if d.decision in ("CARE", "THANK") and d.requires_human_review != "Yes":
            d.requires_human_review = "Yes"; checks.append({"check": "human_review_forced", "result": "FIXED"})
        if d.decision == "CARE":
            if not d.human_staff_id:
                d.human_staff_id, d.human_role = "ST02", "Care Pastor"
                checks.append({"check": "care_owner", "result": "FIXED"})
            d.follow_up_days = d.follow_up_days or C.CARE_FOLLOW_UP_DAYS

        # 5. A thank-you must contain no ask
        if d.decision == "THANK" and d.draft and ASK_LANGUAGE.search(d.draft.split("\n—")[0]):
            checks.append({"check": "thank_you_has_no_ask", "result": "FAIL", "matched": ASK_LANGUAGE.search(d.draft).group(0)})
            d.draft = ""  # drop the draft; the human writes it from scratch
        elif d.decision == "THANK":
            checks.append({"check": "thank_you_has_no_ask", "result": "PASS"})

        d.trace.append({"agent": self.name, "checks": checks, "final": [d.decision, d.automation_action]})
        return d

"""Orchestrator: runs the agents in a fixed order for each scheduled automation and fails closed."""
from dataclasses import asdict
from .schemas import Decision
from .agents.signals import SignalAgent
from .agents.detector import SacredMomentDetector
from .agents.decision import DecisionAgent
from .agents.routing import RoutingAgent


class Orchestrator:
    def __init__(self, detector=None, routing=None, guardrail=None, drafter=None):
        self.signals = SignalAgent()
        self.detector = detector or SacredMomentDetector()
        self.decider = DecisionAgent()
        self.router = routing or RoutingAgent()
        self.guardrail = guardrail
        self.drafter = drafter

    def run_member(self, bundle: dict, automation_ids=None) -> list[Decision]:
        autos = bundle.get("scheduled_automation", [])
        if automation_ids:
            autos = [a for a in autos if a["automation_id"] in automation_ids]
        try:
            facts = self.signals.run(bundle)
            facts = self.detector.run(facts)
        except Exception as e:
            return [self._fail_closed(bundle, a, f"signal/detector error: {e}") for a in autos]
        trace_items = [{"kind": it.kind, "id": it.item_id, "on": it.on, "days_ago": it.days_ago, "consent": it.consent,
                        "label": asdict(it.label) if it.label else None} for it in facts["items"]]
        out = []
        for a in autos:
            try:
                d = self.decider.run(facts, a)
                d.trace.append({"agent": "SacredMomentDetector", "labels": trace_items})
                d.trace.append({"agent": "DecisionAgent", "rule": d.rule, "decision": d.decision, "action": d.automation_action})
                d = self.router.run(facts, d)
                if d.human_staff_id:
                    d.trace.append({"agent": "RoutingAgent", "staff_id": d.human_staff_id, "why": d.human_reason})
                if self.drafter:
                    d = self.drafter.run(facts, a, d)
                if self.guardrail:
                    d = self.guardrail.run(facts, a, d)
                out.append(d.validate())
            except Exception as e:
                out.append(self._fail_closed(bundle, a, f"decision error: {e}"))
        return out

    @staticmethod
    def _fail_closed(bundle, auto, why):
        d = Decision(automation_id=auto.get("automation_id", "?"), member_id=bundle.get("member", {}).get("member_id", "?"),
                     decision="WAIT", automation_action="BLOCK", sacred_detected="Uncertain",
                     guardrail_result="BLOCK", guardrail_trigger="SYSTEM_ERROR", requires_human_review="Yes",
                     rule="FAIL_CLOSED", reason=f"Kairos hit an error and held the message for a person to check ({why}).")
        d.trace.append({"agent": "Orchestrator", "error": why})
        return d

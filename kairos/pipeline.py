"""Wires the agents together with reference data loaded from the CSVs."""
import csv
from .config import DATA_DIR
from .orchestrator import Orchestrator
from .agents.detector import SacredMomentDetector
from .agents.routing import RoutingAgent
from .agents.guardrail import GuardrailAgent
from .agents.drafter import DraftAgent


def load_staff():
    with open(DATA_DIR / "staff.csv") as f:
        return {r["staff_id"]: r for r in csv.DictReader(f)}


def load_last_contact():
    with open(DATA_DIR / "relationship_strength.csv") as f:
        return {(r["member_id"], r["staff_id"]): r["last_contact_date"] for r in csv.DictReader(f)}


def build_orchestrator(mode: str = "keyword") -> Orchestrator:
    staff = load_staff()
    return Orchestrator(detector=SacredMomentDetector(mode=mode),
                        routing=RoutingAgent(staff, load_last_contact()),
                        drafter=DraftAgent(staff),
                        guardrail=GuardrailAgent())

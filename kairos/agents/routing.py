"""RoutingAgent: the right human is the person with the strongest relationship, explained, not just scored."""
from ..schemas import Decision


class RoutingAgent:
    name = "RoutingAgent"

    def __init__(self, staff: dict | None = None, last_contact: dict | None = None):
        self.staff = staff or {}                 # staff_id -> {name, role, weekly_care_capacity}
        self.last_contact = last_contact or {}   # (member_id, staff_id) -> ISO date

    def run(self, facts: dict, d: Decision) -> Decision:
        if d.decision not in ("CARE", "THANK"):
            return d
        cands = facts.get("relationship_candidates") or []
        if not cands:
            # No known relationship: fall back to the Care Pastor rather than leaving it unassigned.
            d.human_staff_id, d.human_role = "ST02", "Care Pastor"
            d.human_reason = "No relationship on file, so it goes to the Care Pastor by default."
            return d
        # Highest strength; ties broken by most recent contact, then staff_id for determinism.
        mid = facts["member"]["member_id"]
        best = max(cands, key=lambda r: (r["strength_pct"], self.last_contact.get((mid, r["staff_id"]), ""), r["staff_id"]))
        d.human_staff_id, d.human_role = best["staff_id"], best["role"]
        name = self.staff.get(best["staff_id"], {}).get("name", best["staff_id"])
        last = self.last_contact.get((mid, best["staff_id"]))
        runner = sorted(cands, key=lambda r: -r["strength_pct"])[1:2]
        d.human_reason = (f"{name} ({best['role']}) has the strongest relationship ({best['strength_pct']}%)"
                          + (f", last in contact {last}" if last else "")
                          + (f". Next closest: {runner[0]['role']} at {runner[0]['strength_pct']}%." if runner else "."))
        return d

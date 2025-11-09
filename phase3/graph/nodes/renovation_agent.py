from typing import Dict

from sqlalchemy import select

from ..state import GraphState, AgentResult
from smartestate.db import session_scope
from smartestate.models import Property


COST_TABLE = {
    "bedroom": 120000,  # paint, flooring, wardrobe baseline
    "bathroom": 150000,  # plumbing + tiles + fittings
    "kitchen": 200000,   # cabinets + countertop + plumbing
    "living_room": 100000,
}


def _estimate(parsed: Dict) -> Dict:
    total = 0
    breakdown = {}
    if not parsed:
        return {"total": None, "breakdown": breakdown}
    for item in parsed.get("rooms_detail", []):
        label = (item.get("label") or "").lower().replace(" ", "_")
        count = int(item.get("count") or 0)
        if label in COST_TABLE:
            c = COST_TABLE[label] * count
            breakdown[label] = breakdown.get(label, 0) + c
            total += c
    return {"total": total, "breakdown": breakdown}


def renovation_node(state: GraphState) -> GraphState:
    # expects a property id mentioned like PROP-xxxxx
    text = state.messages[-1].content if state.messages else ""
    pid = None
    for tok in text.replace("\n", " ").split():
        if tok.upper().startswith("PROP-"):
            pid = tok.upper()
            break
    est = {"total": None, "breakdown": {}}
    if pid:
        with session_scope() as s:
            rec = s.execute(select(Property).where(Property.external_id == pid)).scalar_one_or_none()
            if rec and rec.parsed_json:
                est = _estimate(rec.parsed_json)
    lines = [f"Estimated renovation cost: ₹{est['total']:,}" if est.get("total") else "Not enough data to estimate."]
    state.result = AgentResult(text="\n".join(lines), data={"estimate": est})
    return state

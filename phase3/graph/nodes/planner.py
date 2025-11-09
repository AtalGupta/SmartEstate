from typing import List, Dict, Any
import json

from ..state import GraphState, PlanStep
from smartestate.tools.llm_provider import get_llm


def extract_preferences(text: str) -> Dict[str, Any]:
    low = text.lower()
    prefs: Dict[str, Any] = {}
    # simple extractors
    for loc in ["hyderabad", "mumbai", "delhi", "pune", "bangalore"]:
        if loc in low:
            prefs.setdefault("preferred_locations", []).append(loc.capitalize())
            break
    if "2bhk" in low:
        prefs["min_bedrooms"] = max(2, prefs.get("min_bedrooms", 0))
    if "3bhk" in low:
        prefs["min_bedrooms"] = max(3, prefs.get("min_bedrooms", 0))
    if "under" in low or "below" in low:
        # naive extract digits before 'l'
        for tok in low.split():
            t = tok.strip()
            if t.endswith("l") and t[:-1].replace('.', '', 1).isdigit():
                prefs["budget_max"] = float(t[:-1]) * 100000
                break
    return prefs


def planner_node(state: GraphState) -> GraphState:
    text = state.messages[-1].content if state.messages else ""
    # Try LLM-based structured extraction first
    prefs: Dict[str, Any] = {}
    steps: List[PlanStep] = []
    llm = get_llm(default_to_fake=True)
    if llm is not None:
        schema = (
            "You are a planner. Extract user preferences and propose an execution plan as JSON.\n"
            "Fields: {\n"
            "  \"budget_max_rupees\": number|null,\n"
            "  \"preferred_locations\": string[]|null,\n"
            "  \"min_bedrooms\": number|null,\n"
            "  \"steps\": string[]  // sequence of: recall, sql, rag, renovation, report\n"
            "}\n"
            "Only output JSON."
        )
        try:
            msg = llm.invoke(schema + "\nUser: " + text)
            content = getattr(msg, "content", str(msg))
            data = json.loads(content)
            if isinstance(data, dict):
                if data.get("budget_max_rupees"):
                    prefs["budget_max"] = float(data["budget_max_rupees"])
                if data.get("preferred_locations"):
                    prefs["preferred_locations"] = data["preferred_locations"]
                if data.get("min_bedrooms"):
                    prefs["min_bedrooms"] = int(data["min_bedrooms"])
                for s in data.get("steps", []) or []:
                    if s in {"recall", "sql", "rag", "renovation", "report"}:
                        steps.append(PlanStep(name=s))
        except Exception:
            prefs = {}
            steps = []

    # Fallback or merge with rule-based
    rb = extract_preferences(text)
    prefs = {**rb, **prefs}
    # Always start with recall for memory-aware behavior
    if not steps:
        steps = [PlanStep(name="recall")]
        if "budget_max" in prefs or "preferred_locations" in prefs:
            steps.append(PlanStep(name="sql"))
        steps.append(PlanStep(name="rag"))
        if "PROP-" in text.upper():
            steps.append(PlanStep(name="renovation"))
        steps.append(PlanStep(name="report"))

    existing = state.context.get("memory", {}) if state.context else {}
    merged = {**existing, **prefs}
    state.context["memory"] = merged
    state.plan = steps
    state.plan_idx = 0
    return state

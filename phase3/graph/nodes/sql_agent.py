import json
from typing import Dict, Any

from langchain_core.prompts import ChatPromptTemplate

from smartestate.tools.sql import find_properties
from smartestate.tools.llm_provider import get_llm
from ..prompts import SQL_SUMMARY_PROMPT
from ..state import GraphState, AgentResult, Citation


def sql_node(state: GraphState) -> GraphState:
    text = state.messages[-1].content if state.messages else ""
    # naive filter extraction
    params: Dict[str, Any] = {}
    low = text.lower()

    # Extract price
    if "under" in low or "below" in low:
        try:
            nums = [float(s.strip('l')) for s in low.replace("lakh", "l").split() if s.replace('.', '', 1).isdigit() or s.endswith('l')]
            if nums:
                # assume Lakh conversion if suffixed by l
                max_price = nums[0] * (100000 if 'l' in low else 1)
                params["max_price"] = max_price
        except Exception:
            pass

    # Extract location
    for loc_kw in ["hyderabad", "mumbai", "delhi", "pune", "bangalore", "chennai", "kolkata", "jamshedpur", "nagpur"]:
        if loc_kw in low:
            params["location"] = loc_kw.capitalize()
            break

    # Extract BHK intent
    bhk_map = {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5}
    for key, value in bhk_map.items():
        token = f"{key}bhk"
        if token in low or f"{key} bhk" in low:
            params["min_rooms"] = value
            params["max_rooms"] = value
            break

    # apply memory defaults
    mem = state.context.get("memory", {}) if state.context else {}
    if "budget_max" in mem and "max_price" not in params:
        params["max_price"] = mem["budget_max"]
    if mem.get("preferred_locations") and "location" not in params:
        params["location"] = mem["preferred_locations"][0]

    rows = find_properties(params, limit=8)
    citations = [Citation(source_id=r.get("external_id", ""), snippet=r.get("title") or "") for r in rows]

    llm = get_llm()
    if llm and rows:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SQL_SUMMARY_PROMPT),
            ("human", "Question: {question}\nRows JSON:```json\n{rows}\n```"),
        ])
        msgs = prompt.format_messages(question=text, rows=json.dumps(rows, ensure_ascii=False))
        response = llm.invoke(msgs)
        result_text = response.content if hasattr(response, "content") else str(response)
    elif rows:
        lines = [
            f"• {r.get('external_id')}: {r.get('title')} | {r.get('location')} | ₹{(r.get('price') or 0):,.0f}"
            for r in rows
        ]
        result_text = f"Found {len(rows)} properties:\n" + "\n".join(lines)
    else:
        result_text = "No properties found matching your criteria. Try adjusting your search parameters."

    state.result = AgentResult(text=result_text, data={"rows": rows, "count": len(rows)}, citations=citations)
    return state

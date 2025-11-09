from typing import Tuple

from .state import GraphState, Message


KEYWORDS = {
    "sql": ["find", "filter", "under", "price", "location", "2bhk", "3bhk", "list"],
    "rag": ["summarize", "explain", "certificates", "report", "details"],
    "renovation": ["renovation", "estimate", "cost", "budget"],
    "report": ["pdf", "generate report", "summary pdf"],
    "parse_floorplan": ["parse", "floorplan", "analyze image"],
}


def detect_intent(state: GraphState) -> GraphState:
    if not state.messages:
        state.intent = "unknown"
        return state
    last = state.messages[-1].content.lower()
    for intent, words in KEYWORDS.items():
        if any(w in last for w in words):
            state.intent = intent  # type: ignore[assignment]
            break
    else:
        # If multiple categories appear, treat as mixed
        hits = [intent for intent, words in KEYWORDS.items() if any(w in last for w in words)]
        state.intent = "mixed" if len(hits) > 1 else "unknown"
    return state


from ..state import GraphState, AgentResult
from smartestate.tools.memory import search_semantic_memory


def recall_node(state: GraphState) -> GraphState:
    text = state.messages[-1].content if state.messages else ""
    user_id = state.context.get("user_id") if state.context else None
    memories = []
    try:
        if user_id:
            memories = search_semantic_memory(user_id, text, k=3)
    except Exception:
        memories = []
    if memories:
        state.context["recall"] = memories
        lines = [f"Recall: {m.get('text','')[:120]}" for m in memories]
        state.result = AgentResult(text="\n".join(lines), data={"memories": memories})
    return state


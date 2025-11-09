from typing import Literal

from langgraph.graph import StateGraph, END

from .state import GraphState
from .router import detect_intent
from .nodes.sql_agent import sql_node
from .nodes.rag_agent import rag_node
from .nodes.renovation_agent import renovation_node
from .nodes.report_agent import report_node


def build_graph():
    """
    Simplified graph for demo - direct routing without complex planning.
    Routes query to appropriate agent based on intent, then returns result.
    """
    g = StateGraph(GraphState)

    g.add_node("router", detect_intent)
    g.add_node("sql", sql_node)
    g.add_node("rag", rag_node)
    g.add_node("renovation", renovation_node)
    g.add_node("report", report_node)

    g.set_entry_point("router")

    # Simple direct routing based on intent
    def route(state: GraphState) -> Literal["sql", "rag", "renovation", "report"]:
        intent = state.intent
        if intent == "sql":
            return "sql"
        if intent == "renovation":
            return "renovation"
        if intent == "report":
            return "report"
        # Default to RAG for unknown/mixed queries
        return "rag"

    g.add_conditional_edges("router", route, {
        "sql": "sql",
        "rag": "rag",
        "renovation": "renovation",
        "report": "report"
    })

    # All agent nodes go directly to END
    g.add_edge("sql", END)
    g.add_edge("rag", END)
    g.add_edge("renovation", END)
    g.add_edge("report", END)

    return g.compile()

from phase3.graph.state import GraphState, Message
from phase3.graph.router import detect_intent


def test_router_detects_sql_intent():
    s = GraphState(messages=[Message(role="user", content="Find 2BHK in Hyderabad under 70L")])
    out = detect_intent(s)
    assert out.intent in ("sql", "mixed")


def test_router_detects_rag_intent():
    s = GraphState(messages=[Message(role="user", content="Summarize certificates for this property")])
    out = detect_intent(s)
    assert out.intent == "rag"


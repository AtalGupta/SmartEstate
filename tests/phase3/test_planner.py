import json
import types

from phase3.graph.nodes.planner import planner_node
from phase3.graph.state import GraphState, Message


class DummyLLM:
    def __init__(self, response: str):
        self._resp = response

    def invoke(self, *_args, **_kwargs):
        return types.SimpleNamespace(content=self._resp)


def test_planner_rule_based_extraction_when_no_llm(monkeypatch):
    # Force get_llm to return None
    import phase3.graph.nodes.planner as planner
    monkeypatch.setattr(planner, "get_llm", lambda default_to_fake=True: None)
    s = GraphState(messages=[Message(role="user", content="Find 2BHK in Hyderabad under 70L")])
    out = planner_node(s)
    mem = out.context.get("memory", {})
    assert mem.get("budget_max") == 7000000
    assert mem.get("preferred_locations") == ["Hyderabad"]
    assert any(step.name in ("recall", "sql", "rag", "report") for step in out.plan)


def test_planner_llm_structured_extraction(monkeypatch):
    # Provide an LLM that returns JSON with preferences and steps
    import phase3.graph.nodes.planner as planner
    resp = json.dumps({
        "budget_max_rupees": 6500000,
        "preferred_locations": ["Hyderabad"],
        "min_bedrooms": 2,
        "steps": ["recall", "sql", "rag", "report"]
    })
    monkeypatch.setattr(planner, "get_llm", lambda default_to_fake=True: DummyLLM(resp))
    s = GraphState(messages=[Message(role="user", content="Need flats below 65L in Hyderabad")])
    out = planner_node(s)
    mem = out.context.get("memory", {})
    assert mem.get("budget_max") == 6500000
    assert mem.get("preferred_locations") == ["Hyderabad"]
    assert [st.name for st in out.plan] == ["recall", "sql", "rag", "report"]


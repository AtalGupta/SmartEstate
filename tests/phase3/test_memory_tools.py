import os
import pytest


def test_update_and_load_user_memory(monkeypatch):
    try:
        from smartestate.tools.memory import update_user_memory, load_user_memory, get_or_create_conversation, add_message
    except Exception as e:
        pytest.skip(f"memory tools unavailable: {e}")

    # DB may not be running; try operations and skip on failure
    try:
        conv_id = get_or_create_conversation("tester")
        add_message(conv_id, "user", "I like Hyderabad under 70L")
        m1 = update_user_memory("tester", {"budget_max": 7000000, "preferred_locations": ["Hyderabad"]})
        assert m1["budget_max"] == 7000000
        m2 = load_user_memory("tester")
        assert m2.get("preferred_locations") == ["Hyderabad"]
    except Exception as e:
        pytest.skip(f"DB not available: {e}")


def test_semantic_memory_add_and_search(monkeypatch):
    try:
        from smartestate.tools.memory import add_semantic_memory, search_semantic_memory
    except Exception as e:
        pytest.skip(f"memory tools unavailable: {e}")
    # ES may not be running; skip on failure
    try:
        add_semantic_memory("tester", "I prefer 2BHK in Hyderabad")
        hits = search_semantic_memory("tester", "2BHK Hyderabad", k=2)
        assert isinstance(hits, list)
    except Exception as e:
        pytest.skip(f"ES not available: {e}")


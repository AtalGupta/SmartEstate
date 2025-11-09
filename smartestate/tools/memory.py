from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional, List

from sqlalchemy import select

from ..db import session_scope
from ..models import Conversation, ChatMessage, UserMemory, Shortlist
from ..es_client import get_es, ensure_memory_index
from ..embedding import Embeddings
from ..config import get_settings


def get_or_create_conversation(user_id: str) -> int:
    with session_scope() as s:
        conv = s.execute(select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.id.desc())).scalar_one_or_none()
        if conv:
            return conv.id
        conv = Conversation(user_id=user_id)
        s.add(conv)
        s.flush()
        return conv.id


def add_message(conversation_id: int, role: str, content: str, tool_calls: Optional[Dict[str, Any]] = None):
    with session_scope() as s:
        m = ChatMessage(conversation_id=conversation_id, role=role, content=content, tool_calls=tool_calls)
        s.add(m)


def load_user_memory(user_id: str) -> Dict[str, Any]:
    with session_scope() as s:
        rec = s.execute(select(UserMemory).where(UserMemory.user_id == user_id)).scalar_one_or_none()
        return rec.data if rec else {}


def update_user_memory(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    with session_scope() as s:
        rec = s.execute(select(UserMemory).where(UserMemory.user_id == user_id)).scalar_one_or_none()
        if rec is None:
            rec = UserMemory(user_id=user_id, data=updates)
            s.add(rec)
        else:
            data = rec.data or {}
            data.update({k: v for k, v in updates.items() if v is not None})
            rec.data = data
        return rec.data


def remember_shortlist(user_id: str, property_ids: List[str]) -> List[str]:
    with session_scope() as s:
        rec = s.execute(select(Shortlist).where(Shortlist.user_id == user_id)).scalar_one_or_none()
        if rec is None:
            rec = Shortlist(user_id=user_id, properties={"ids": property_ids})
            s.add(rec)
            return property_ids
        ids = set(rec.properties.get("ids", []))
        for pid in property_ids:
            ids.add(pid)
        rec.properties = {"ids": list(ids)}
        return rec.properties["ids"]


def add_semantic_memory(user_id: str, text: str):
    es = get_es()
    idx = ensure_memory_index(es)
    settings = get_settings()
    embedder = Embeddings(settings.embedding_model)
    vec = (embedder.embed([text]) or [None])[0]
    doc = {"user_id": user_id, "text": text, "created_at": datetime.utcnow().isoformat()}
    if vec is not None:
        doc["embedding"] = vec
    es.index(index=idx, document=doc)


def search_semantic_memory(user_id: str, query: str, k: int = 3):
    es = get_es()
    idx = ensure_memory_index(es)
    settings = get_settings()
    embedder = Embeddings(settings.embedding_model)
    vec = (embedder.embed([query]) or [None])[0]
    if vec is not None:
        body = {
            "size": k,
            "knn": {
                "field": "embedding",
                "query_vector": vec,
                "k": k,
                "num_candidates": max(10, k * 4)
            },
            "query": {"term": {"user_id": user_id}}
        }
    else:
        body = {
            "size": k,
            "query": {
                "bool": {
                    "must": {"multi_match": {"query": query, "fields": ["text"]}},
                    "filter": {"term": {"user_id": user_id}}
                }
            }
        }
    res = es.search(index=idx, body=body)
    out = []
    for h in res.get("hits", {}).get("hits", []):
        out.append({"id": h.get("_id"), **(h.get("_source") or {})})
    return out

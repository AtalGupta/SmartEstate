from typing import List, Dict, Any

from ..es_client import get_es
from ..config import get_settings
from ..embedding import Embeddings


def search_properties(query: str, k: int = 5, needs_certificate: bool = False) -> List[Dict[str, Any]]:
    es = get_es()
    settings = get_settings()
    index = settings.elasticsearch_index
    embedder = Embeddings(settings.embedding_model)
    vectors = embedder.embed([query]) or [None]
    vector = vectors[0]

    filters: List[Dict[str, Any]] = []
    if needs_certificate:
        filters.append({"exists": {"field": "cert_links"}})

    if vector is not None:
        knn_body: Dict[str, Any] = {
            "field": "embedding",
            "query_vector": vector,
            "k": k,
            "num_candidates": max(20, k * 5),
        }
        if filters:
            knn_body["filter"] = {"bool": {"filter": filters}}
        body = {"size": k, "knn": knn_body}
    else:
        match_query: Dict[str, Any] = {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "long_description", "full_text"],
                "type": "best_fields",
            }
        }
        if filters:
            match_query = {"bool": {"must": match_query, "filter": filters}}
        body = {"size": k, "query": match_query}

    res = es.search(index=index, body=body)
    out: List[Dict[str, Any]] = []
    for hit in res.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        out.append({
            "id": hit.get("_id"),
            "score": hit.get("_score"),
            **source,
        })
    return out

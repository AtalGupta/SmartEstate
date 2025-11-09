from typing import Optional

from elasticsearch import Elasticsearch

from .config import get_settings


def get_es() -> Elasticsearch:
    settings = get_settings()
    return Elasticsearch(settings.elasticsearch_url)


def ensure_index(es: Optional[Elasticsearch] = None):
    settings = get_settings()
    es = es or get_es()
    index = settings.elasticsearch_index
    if es.indices.exists(index=index):
        return
    mapping = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "title": {"type": "text"},
                "long_description": {"type": "text"},
                "location": {"type": "keyword"},
                "price": {"type": "double"},
                "listing_date": {"type": "date"},
                "seller_type": {"type": "keyword"},
                "metadata_tags": {"type": "keyword"},
                "parsed_json": {"type": "object", "enabled": True},
                "rooms_detail": {"type": "nested"},
                "full_text": {"type": "text"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    es.indices.create(index=index, body=mapping)


def ensure_memory_index(es: Optional[Elasticsearch] = None):
    settings = get_settings()
    es = es or get_es()
    index = f"{settings.elasticsearch_index}_memory"
    if es.indices.exists(index=index):
        return index
    mapping = {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "user_id": {"type": "keyword"},
                "text": {"type": "text"},
                "embedding": {"type": "dense_vector", "dims": 384, "index": True, "similarity": "cosine"},
                "created_at": {"type": "date"}
            }
        }
    }
    es.indices.create(index=index, body=mapping)
    return index

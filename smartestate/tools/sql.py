from typing import Dict, Any, List

from sqlalchemy import select, and_, func, Integer

from ..db import session_scope
from ..models import Property


ALLOWED_FIELDS = {"location", "seller_type"}


def find_properties(filters: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    clauses = []
    if "max_price" in filters:
        clauses.append(Property.price <= float(filters["max_price"]))
    if "min_price" in filters:
        clauses.append(Property.price >= float(filters["min_price"]))
    if "location" in filters and filters["location"]:
        # Use LIKE for partial matching since location contains full address
        clauses.append(Property.location.ilike(f"%{str(filters['location'])}%"))
    if "seller_type" in filters and filters["seller_type"] in {"owner", "builder", "agent"}:
        clauses.append(Property.seller_type == filters["seller_type"])

    # Filter by BHK/rooms using JSON field
    if "min_rooms" in filters:
        clauses.append(func.cast(Property.parsed_json["rooms"], Integer) >= int(filters["min_rooms"]))
    if "max_rooms" in filters:
        clauses.append(func.cast(Property.parsed_json["rooms"], Integer) <= int(filters["max_rooms"]))

    with session_scope() as s:
        q = select(Property).where(and_(*clauses)) if clauses else select(Property)
        q = q.limit(limit)
        rows = s.execute(q).scalars().all()
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append({
                "external_id": r.external_id,
                "title": r.title,
                "location": r.location,
                "price": r.price,
                "seller_type": r.seller_type,
                "listing_date": r.listing_date.isoformat() if r.listing_date else None,
                "seller_contact": r.seller_contact,
                "cert_links": r.cert_links,
                "long_description": r.long_description,
                "parsed": r.parsed_json,
            })
        return out

import hashlib
import os
import tempfile
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from pypdf import PdfReader
from sqlalchemy import select

from .config import get_settings
from .db import session_scope, init_db
from .embedding import Embeddings
from .es_client import get_es, ensure_index
from .floorplan import FloorplanParser
from .models import Property


def _stable_id(*parts: str) -> str:
    base = "::".join([p or "" for p in parts])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()  # nosec B324


def _ensure_local(path_or_url: str) -> Optional[str]:
    if not path_or_url:
        return None
    if path_or_url.lower().startswith("http://") or path_or_url.lower().startswith("https://"):
        try:
            with requests.get(path_or_url, timeout=20) as r:
                r.raise_for_status()
                fd, tmp = tempfile.mkstemp(prefix="smartestate_")
                with os.fdopen(fd, "wb") as f:
                    f.write(r.content)
                return tmp
        except Exception:
            return None
    if os.path.exists(path_or_url):
        return path_or_url
    return None


def _read_pdfs_text(paths: List[str]) -> str:
    texts: List[str] = []
    for p in paths:
        local = _ensure_local(p)
        if not local or not os.path.exists(local):
            continue
        try:
            reader = PdfReader(local)
            for page in reader.pages:
                t = page.extract_text() or ""
                if t:
                    texts.append(t)
        except Exception:
            continue
    return "\n".join(texts)


def _parse_cert_links(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        if raw.lower() == "nan" or not raw.strip():
            return []
        # support pipe or comma separated filenames/links
        sep = "|" if "|" in raw else ","
        parts = [x.strip() for x in raw.split(sep)]
        return [p for p in parts if p]
    return []


def _to_date(val: Any) -> Optional[date]:
    try:
        if pd.isna(val):
            return None
        if isinstance(val, datetime):
            return val.date()
        return pd.to_datetime(val).date()
    except Exception:
        return None


def _resolve_image_path(image_name_or_path: Optional[str]) -> Optional[str]:
    if not image_name_or_path or str(image_name_or_path).lower() == "nan":
        return None
    # If this is already a path or URL, delegate to _ensure_local
    if os.path.sep in image_name_or_path or image_name_or_path.lower().startswith(("http://", "https://")):
        return _ensure_local(image_name_or_path)
    # Try common assets dirs
    candidates = [
        os.path.join("assets", "images", image_name_or_path),
        os.path.join("assets", "train", image_name_or_path),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _resolve_certificate_paths(names_or_links: List[str]) -> List[str]:
    out: List[str] = []
    for n in names_or_links:
        if n.lower().startswith(("http://", "https://")) or os.path.sep in n:
            out.append(n)
        else:
            cand = os.path.join("assets", "certificates", n)
            out.append(cand if os.path.exists(cand) else n)
    return out


def ingest_excel(file_path: str) -> Dict[str, Any]:
    settings = get_settings()
    init_db()
    ensure_index()

    df = pd.read_excel(file_path)
    cols = {c.lower().strip(): c for c in df.columns}

    # Map to dataset columns
    col_title = cols.get("title")
    col_desc = cols.get("long_description") or cols.get("description")
    col_loc = cols.get("location") or cols.get("city")
    col_price = cols.get("price")
    col_date = cols.get("listing_date") or cols.get("date")
    col_img = cols.get("floorplan_image") or cols.get("image") or cols.get("image_url") or cols.get("image_file")
    col_certs = cols.get("cert_links") or cols.get("certificates") or cols.get("certifications")
    col_seller_type = cols.get("seller_type")
    col_seller_contact = cols.get("seller_contact")
    col_tags = cols.get("metadata_tags")
    col_ext_id = cols.get("id") or cols.get("external_id") or cols.get("property_id")

    parser = FloorplanParser()
    embedder = Embeddings(settings.embedding_model)
    es = get_es()

    successes, failures = 0, 0
    indexed, skipped = 0, 0

    with session_scope() as session:
        for _, row in df.iterrows():
            try:
                title = str(row[col_title]).strip() if col_title else None
                desc = str(row[col_desc]).strip() if col_desc else None
                loc = str(row[col_loc]).strip() if col_loc else None
                price = float(row[col_price]) if col_price and not pd.isna(row[col_price]) else None
                ldate = _to_date(row[col_date]) if col_date else None
                img_val = str(row[col_img]).strip() if col_img else None
                img = img_val
                certs = _parse_cert_links(row[col_certs]) if col_certs else []
                external_id = str(row[col_ext_id]).strip() if col_ext_id else _stable_id(title or "", loc or "", str(price or ""))
                seller_type = str(row[col_seller_type]).strip() if col_seller_type else None
                seller_contact = str(row[col_seller_contact]).strip() if col_seller_contact else None
                tags_raw = str(row[col_tags]).strip() if col_tags else None
                tags = None
                if tags_raw and tags_raw.lower() != "nan":
                    sep = "|" if "|" in tags_raw else ","
                    tags = {"tags": [t.strip() for t in tags_raw.split(sep) if t.strip()]}

                local_img = _resolve_image_path(img)
                parsed_json = None
                if local_img and os.path.exists(local_img):
                    try:
                        parsed_json = parser.parse(local_img)
                    except Exception:
                        parsed_json = None

                cert_paths = _resolve_certificate_paths(certs)
                cert_text = _read_pdfs_text([c for c in cert_paths if c.lower().endswith(".pdf")])

                existing = session.execute(select(Property).where(Property.external_id == external_id)).scalar_one_or_none()
                if existing is None:
                    rec = Property(
                        external_id=external_id,
                        title=title,
                        long_description=desc,
                        location=loc,
                        price=price,
                        listing_date=ldate,
                        floorplan_image=img,
                        seller_type=seller_type,
                        seller_contact=seller_contact,
                        metadata_tags=tags,
                        cert_links={"links": cert_paths} if certs else None,
                        parsed_json=parsed_json,
                    )
                    session.add(rec)
                else:
                    existing.title = title
                    existing.long_description = desc
                    existing.location = loc
                    existing.price = price
                    existing.listing_date = ldate
                    existing.floorplan_image = img
                    existing.seller_type = seller_type
                    existing.seller_contact = seller_contact
                    existing.metadata_tags = tags
                    existing.cert_links = {"links": cert_paths} if certs else None
                    existing.parsed_json = parsed_json or existing.parsed_json
                successes += 1

                # Build ES doc
                full_text_parts = [p for p in [title, desc, cert_text] if p]
                full_text = "\n\n".join(full_text_parts)
                embedding = None
                if full_text:
                    vecs = embedder.embed([full_text])
                    embedding = vecs[0] if vecs else None
                doc = {
                    "title": title,
                    "long_description": desc,
                    "location": loc,
                    "price": price,
                    "listing_date": ldate.isoformat() if ldate else None,
                    "seller_type": seller_type,
                    "metadata_tags": (tags or {}).get("tags") if tags else None,
                    "parsed_json": parsed_json,
                    "rooms_detail": (parsed_json or {}).get("rooms_detail") if parsed_json else None,
                    "full_text": full_text or None,
                }
                if embedding is not None:
                    doc["embedding"] = embedding
                try:
                    es.index(index=settings.elasticsearch_index, id=external_id, document=doc)
                    indexed += 1
                except Exception:
                    skipped += 1

            except Exception:
                failures += 1
                continue

    return {
        "ingested_rows": successes,
        "failed_rows": failures,
        "indexed_docs": indexed,
        "skipped_index": skipped,
    }

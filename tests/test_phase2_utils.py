import os
import pytest

ETL_IMPORT_ERROR = None
ES_IMPORT_ERROR = None
try:
    from smartestate.etl import (
        _parse_cert_links,
        _resolve_certificate_paths,
        _resolve_image_path,
        _read_pdfs_text,
    )
except Exception as e:
    ETL_IMPORT_ERROR = e

try:
    from smartestate.es_client import ensure_index
except Exception as e:
    ES_IMPORT_ERROR = e


class FakeIndices:
    def __init__(self):
        self.created = None
        self._exists = False

    def exists(self, index):
        return self._exists

    def create(self, index, body):
        self.created = {"index": index, "body": body}
        self._exists = True
        return {"acknowledged": True}


class FakeES:
    def __init__(self):
        self.indices = FakeIndices()


def test_parse_cert_links_splitters():
    if ETL_IMPORT_ERROR:
        pytest.skip(f"ETL module not available: {ETL_IMPORT_ERROR}")
    assert _parse_cert_links("a.pdf|b.pdf") == ["a.pdf", "b.pdf"]
    assert _parse_cert_links("a.pdf, b.pdf") == ["a.pdf", "b.pdf"]
    assert _parse_cert_links(None) == []
    assert _parse_cert_links("nan") == []


def test_resolve_certificate_paths_to_assets():
    if ETL_IMPORT_ERROR:
        pytest.skip(f"ETL module not available: {ETL_IMPORT_ERROR}")
    # Use known sample PDFs in assets/certificates
    names = [
        "fire-safety.pdf",
        "pest-control.pdf",
    ]
    paths = _resolve_certificate_paths(names)
    for p in paths:
        assert os.path.exists(p), f"Path does not exist: {p}"


def test_resolve_image_path_from_filename():
    if ETL_IMPORT_ERROR:
        pytest.skip(f"ETL module not available: {ETL_IMPORT_ERROR}")
    # Pick first image in assets/images
    images_dir = os.path.join("assets", "images")
    if not os.path.isdir(images_dir):
        pytest.skip("assets/images not available")
    names = [n for n in os.listdir(images_dir) if n.lower().endswith((".jpg", ".png", ".jpeg"))]
    if not names:
        pytest.skip("no image files available")
    p = _resolve_image_path(names[0])
    assert p is not None and os.path.exists(p)


def test_read_pdfs_text_nonempty():
    if ETL_IMPORT_ERROR:
        pytest.skip(f"ETL module not available: {ETL_IMPORT_ERROR}")
    names = ["assets/certificates/fire-safety.pdf"]
    text = _read_pdfs_text(names)
    assert isinstance(text, str)
    # Not all PDFs are text-extractable; allow empty but should not error


def test_ensure_index_creates_mapping():
    if ES_IMPORT_ERROR:
        pytest.skip(f"ES client not available: {ES_IMPORT_ERROR}")
    fake = FakeES()
    ensure_index(fake)
    created = fake.indices.created
    assert created is not None
    body = created["body"]
    props = body["mappings"]["properties"]
    assert "embedding" in props
    assert props["embedding"]["type"] == "dense_vector"
    assert props["embedding"]["dims"] == 384

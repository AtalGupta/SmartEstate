import os
import pytest


def test_phase1_wrapper_and_parse_smoke():
    try:
        from smartestate.floorplan import FloorplanParser
    except Exception as e:
        pytest.skip(f"Phase 1 dependencies not available: {e}")
    # Ensure model artifacts exist
    model_dir = os.environ.get("MODEL_DIR", "kaggle/working")
    infer_path = os.path.join(model_dir, "inference_production.py")
    meta_path = os.path.join(model_dir, "models", "model_metadata.json")
    if not (os.path.exists(infer_path) and os.path.exists(meta_path)):
        pytest.skip("Phase 1 artifacts not present; skipping")

    # Pick a sample image from assets/images
    assets_dir = os.path.join("assets", "images")
    if not os.path.isdir(assets_dir):
        pytest.skip("assets/images not found")
    sample_images = [f for f in os.listdir(assets_dir) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
    if not sample_images:
        pytest.skip("No images in assets/images")
    image_path = os.path.join(assets_dir, sample_images[0])

    parser = FloorplanParser()
    try:
        result = parser.parse(image_path)
    except RuntimeError:
        # Fallback: offline environment without EasyOCR models.
        # Inject a dummy OCR to exercise detection + fallback logic without network.
        class _DummyOCR:
            def readtext(self, *args, **kwargs):
                return []

        # Monkeypatch: force OCR to dummy and bypass _load_ocr
        parser._ocr = _DummyOCR()
        parser._load_ocr = lambda: None  # type: ignore[assignment]
        result = parser.parse(image_path)

    # Basic structure assertions
    assert isinstance(result, dict)
    for k in ["rooms", "halls", "kitchens", "bathrooms", "rooms_detail", "total_detections"]:
        assert k in result
    assert isinstance(result["rooms_detail"], list)
    assert result["rooms"] >= 0 and result["bathrooms"] >= 0

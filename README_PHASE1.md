# Phase 1 – Floorplan Model Snapshot

This phase explains how floorplan rasters are transformed into structured JSON before the ETL and agent layers. The exploratory notebook (`kaggle/working/phase1_floorplan_model_production.ipynb`) contains detailed experiments; this summary captures the essentials required for review.

## Dataset & Split
- Source folders: `assets/train/` (COCO annotations) and `assets/images/` (hold-out evaluation).
- Split: 80% train / 20% validation by image id, balanced across room-count buckets.
- Augmentations: random horizontal flip, mild brightness jitter, resize to 640×640.

## Model & Training Configuration
- Architecture: Faster R-CNN (ResNet50-FPN) fine-tuned in PyTorch; detections feed EasyOCR.
- OCR rules: ignore furniture tokens such as `2*bed`, leverage `n bhk` hints, persist overlay images for QA.
- Hyperparameters: batch size 4, epochs 15, LR 0.005 with StepLR (γ=0.1 every 5 epochs), weight decay 5e-4.
- Metrics logged:
  - Mean IoU @0.5 on validation split (see `kaggle/working/outputs/performance_report.md`).
  - Count accuracy comparing parsed JSON vs. labeled counts on the hold-out set.
  - Loss curves in `kaggle/working/outputs/training_curves.png`.

## Delivered Artifacts
- Inference script: `kaggle/working/inference_production.py`.
- Weights: `kaggle/working/models/best_model.pth` (training checkpoint) and optional `floorplan_model_inference.pth` via `scripts/convert_checkpoint_to_inference.py`.
- Metadata: `kaggle/working/models/model_metadata.json` (category map, `num_classes`).

## Running Inference
```bash
uv run python - <<'PY'
from smartestate.floorplan import FloorplanParser
parser = FloorplanParser()
print(parser.parse('assets/images/sample.jpg'))
PY
```
The parser returns structured JSON plus `outputs/overlays/<image>_overlay.jpg` for interpretability.

## Notes
- Verify EasyOCR weights with `uv run python scripts/prepare_easyocr_models.py` before running inference.
- The enhanced parser (used in Phase 2 onward) applies identical heuristics so fields like `rooms_detail`, `detected_texts`, and `overlay_path` remain consistent across the pipeline.

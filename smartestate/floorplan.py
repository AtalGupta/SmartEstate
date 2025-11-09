import importlib.util
import json
import os
import re
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch
from torchvision import transforms

from .config import get_settings


class FloorplanParser:
    def __init__(self):
        self.settings = get_settings()
        self._parser_mod = None
        self._model = None
        self._categories = None
        self._ocr = None
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _import_parser_module(self):
        if self._parser_mod is not None:
            return
        # Prefer inference script at model_dir/inference_production.py
        script_path = os.path.join(self.settings.model_dir, "inference_production.py")
        # Fallback: if MODEL_DIR accidentally points to models/, try its parent
        if not os.path.exists(script_path):
            parent = os.path.dirname(self.settings.model_dir.rstrip(os.sep))
            alt = os.path.join(parent, "inference_production.py")
            script_path = alt if os.path.exists(alt) else script_path
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"inference_production.py not found near {self.settings.model_dir}")
        spec = importlib.util.spec_from_file_location("inference_production", script_path)
        if spec is None or spec.loader is None:
            raise ImportError("Cannot import inference_production module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._parser_mod = module

    def _load_metadata(self):
        if self._categories is not None:
            return
        # Metadata is inside models/ under working dir
        meta_path = os.path.join(self.settings.model_dir, "models", "model_metadata.json")
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        self._categories = {cat["id"]: cat["name"] for cat in metadata["categories"]}
        self._num_classes = metadata["num_classes"]

    def _load_model(self):
        if self._model is not None:
            return
        self._import_parser_module()
        self._load_metadata()
        # Ensure PyTorch loads checkpoint with full compatibility on 2.6+
        # Default torch.load weights_only=True can fail on older checkpoints; force legacy behavior safely here.
        os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
        models_dir = os.path.join(self.settings.model_dir, "models")
        preferred = os.path.join(models_dir, "floorplan_model_inference.pth")
        fallback = os.path.join(models_dir, "best_model.pth")
        model_path = preferred if os.path.exists(preferred) else fallback

        # Try robust loader directly (handles both state_dict and full checkpoint dicts)
        try:
            import torch
            from torchvision.models.detection import fasterrcnn_resnet50_fpn
            from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

            model = fasterrcnn_resnet50_fpn(weights=None)
            in_features = model.roi_heads.box_predictor.cls_score.in_features
            model.roi_heads.box_predictor = FastRCNNPredictor(in_features, self._num_classes)

            ckpt = torch.load(model_path, map_location=self._device)
            if isinstance(ckpt, dict) and any(k in ckpt for k in ("model_state_dict", "state_dict")):
                state = ckpt.get("model_state_dict") or ckpt.get("state_dict")
            else:
                state = ckpt
            model.load_state_dict(state, strict=False)
            model.to(self._device)
            model.eval()
            self._model = model
            return
        except Exception:
            # As a last resort, attempt using the Kaggle module's loader (works for raw state_dict)
            try:
                self._model = self._parser_mod.load_model(model_path, self._num_classes, device=self._device)
            except Exception as e:
                raise RuntimeError(f"Failed to load model from {model_path}: {e}")

    def _load_ocr(self):
        if self._ocr is not None:
            return
        try:
            import easyocr  # noqa: F401
            from easyocr import Reader
            langs = self.settings.ocr_langs
            model_dir = self.settings.ocr_model_dir
            # Detect if required weights exist to allow offline init
            required = [
                "craft_mlt_25k.pth",           # detector
                "english_g2.pth",               # recognizer (en)
            ]
            have_all = all(os.path.exists(os.path.join(model_dir, f)) for f in required)
            # Ensure directory exists
            os.makedirs(model_dir, exist_ok=True)
            self._ocr = Reader(
                langs,
                gpu=torch.cuda.is_available(),
                model_storage_directory=model_dir,
                download_enabled=not have_all,
            )
        except Exception:
            self._ocr = None

    def parse(self, image_path: str) -> Dict[str, Any]:
        # Enhanced parse: run detection + OCR with robust text mapping rules and optional overlay image
        self._load_model()
        self._load_ocr()
        if self._ocr is None:
            raise RuntimeError("OCR could not be initialized. Ensure EasyOCR is installed and model files are available.")
        return self._parse_enhanced(image_path, save_overlay=True)

    # ------- Enhanced pipeline helpers -------

    def _run_detection(self, image: Image.Image, threshold: float = 0.5) -> Dict[str, np.ndarray]:
        tensor = transforms.ToTensor()(image).unsqueeze(0).to(self._device)
        with torch.no_grad():
            pred = self._model(tensor)[0]
        scores = pred['scores'].detach().cpu().numpy()
        labels = pred['labels'].detach().cpu().numpy()
        boxes = pred['boxes'].detach().cpu().numpy()
        mask = scores >= threshold
        return {
            'scores': scores[mask],
            'labels': labels[mask],
            'boxes': boxes[mask],
        }

    @staticmethod
    def _normalize_text(t: str) -> str:
        t = t.lower()
        t = re.sub(r"[^a-z0-9\s\-\*]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @staticmethod
    def _parse_bhk(text: str) -> int:
        # Detect patterns like 2bhk / 3 bhk
        m = re.search(r"(\d+)\s*bhk", text)
        return int(m.group(1)) if m else 0

    @staticmethod
    def _is_bedroom_label(text: str) -> bool:
        # treat 'bedroom', 'bed room', 'br' as bedroom; not 'bed' alone
        if 'bedroom' in text or 'bed room' in text:
            return True
        # whole token 'br'
        if re.search(r"\bbr\b", text):
            return True
        return False

    @staticmethod
    def _classify_room(text: str) -> Tuple[str, int]:
        # returns (label, count_increment)
        # handle furniture-like '2*bed' → do not count as bedroom
        if re.search(r"\d+\s*[x\*]\s*bed\b", text):
            return ("bed_furniture", 0)
        if 'kitchen' in text or re.search(r"\bkit\b", text):
            return ("kitchen", 1)
        if any(k in text for k in ['living room', 'living', 'drawing', 'hall']):
            return ("living_room", 1)
        if any(k in text for k in ['bath', 'toilet', 'wc', 'washroom', 'lavatory']):
            return ("bathroom", 1)
        if 'dining' in text:
            return ("dining", 1)
        if 'balcony' in text or 'terrace' in text:
            return ("balcony", 1)
        if FloorplanParser._is_bedroom_label(text):
            return ("bedroom", 1)
        return ("unknown", 0)

    def _overlay(self, img: Image.Image, det: Dict[str, np.ndarray], ocr_notes: List[Tuple[Tuple[int,int,int,int], str]], save_path: str) -> str:
        draw = ImageDraw.Draw(img)
        # simple palette by category
        colors = {
            'room_name': (34, 139, 34),
            'kitchen': (255, 165, 0),
            'bathroom': (70, 130, 180),
            'living_room': (186, 85, 211),
            'unknown': (220, 20, 60),
        }
        for label, box in zip(det['labels'], det['boxes']):
            cat = self._categories.get(int(label), 'unknown')
            x1, y1, x2, y2 = [int(v) for v in box]
            color = colors.get(cat, (255, 255, 0))
            draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=2)
            draw.text((x1+2, y1+2), cat, fill=color)
        # OCR notes
        for (x1, y1, x2, y2), text in ocr_notes:
            draw.text((x1+2, max(0, y1-12)), text[:30], fill=(255, 0, 0))
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        img.save(save_path)
        return save_path

    def _parse_enhanced(self, image_path: str, save_overlay: bool = True) -> Dict[str, Any]:
        img = Image.open(image_path).convert('RGB')
        det = self._run_detection(img)
        img_np = np.array(img)

        room_counts = {
            'bedroom': 0, 'living_room': 0, 'hall': 0,
            'kitchen': 0, 'bathroom': 0, 'dining': 0, 'balcony': 0
        }
        detected_texts: List[str] = []
        ocr_notes: List[Tuple[Tuple[int,int,int,int], str]] = []
        bhk_hint = 0

        # OCR for room_name boxes
        for score, label, box in zip(det['scores'], det['labels'], det['boxes']):
            cat_name = self._categories.get(int(label), 'unknown')
            if cat_name != 'room_name':
                continue
            x1, y1, x2, y2 = [int(v) for v in box]
            pad = 5
            x1, y1 = max(0, x1-pad), max(0, y1-pad)
            x2 = min(img_np.shape[1], x2+pad)
            y2 = min(img_np.shape[0], y2+pad)
            roi = img_np[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            try:
                ocr_results = self._ocr.readtext(roi, detail=1)
                for (_bbox, text, conf) in ocr_results:
                    if conf < 0.3:
                        continue
                    tnorm = self._normalize_text(text)
                    if not tnorm:
                        continue
                    detected_texts.append(tnorm)
                    bhk_hint = max(bhk_hint, self._parse_bhk(tnorm))
                    label_name, inc = self._classify_room(tnorm)
                    if inc > 0:
                        if label_name == 'living_room':
                            room_counts['living_room'] += inc
                        elif label_name == 'bathroom':
                            room_counts['bathroom'] += inc
                        elif label_name == 'kitchen':
                            room_counts['kitchen'] += inc
                        elif label_name == 'dining':
                            room_counts['dining'] += inc
                        elif label_name == 'balcony':
                            room_counts['balcony'] += inc
                        elif label_name == 'bedroom':
                            room_counts['bedroom'] += inc
                    ocr_notes.append(((x1, y1, x2, y2), tnorm))
            except Exception:
                continue

        # Apply BHK hint conservatively
        if bhk_hint and room_counts['bedroom'] < bhk_hint:
            room_counts['bedroom'] = bhk_hint

        # Fallbacks if no OCR-derived counts
        if sum(room_counts.values()) == 0:
            # count number of room_name detections as weak proxy
            num_labels = sum(1 for l in det['labels'] if self._categories.get(int(l)) == 'room_name')
            room_counts['bedroom'] = max(1, num_labels // 3)
            room_counts['living_room'] = 1
            room_counts['kitchen'] = 1
            room_counts['bathroom'] = max(1, num_labels // 5)

        rooms_detail: List[Dict[str, Any]] = []
        for k, display in [
            ('bedroom', 'Bedroom'),
            ('living_room', 'Living Room'),
            ('kitchen', 'Kitchen'),
            ('bathroom', 'Bathroom'),
            ('dining', 'Dining'),
            ('balcony', 'Balcony'),
        ]:
            if room_counts.get(k, 0) > 0:
                rooms_detail.append({'label': display, 'count': int(room_counts[k]), 'approx_area': None})

        overlay_path = None
        if save_overlay:
            base = os.path.splitext(os.path.basename(image_path))[0]
            out_path = os.path.join('outputs', 'overlays', f'{base}_overlay.jpg')
            overlay_path = self._overlay(img.copy(), det, ocr_notes, out_path)

        detection_details = {}
        for l in det['labels']:
            name = self._categories.get(int(l), 'unknown')
            detection_details[name] = detection_details.get(name, 0) + 1

        return {
            'rooms': int(room_counts['bedroom']),
            'halls': int(room_counts['living_room']),
            'kitchens': int(room_counts['kitchen']),
            'bathrooms': int(room_counts['bathroom']),
            'rooms_detail': rooms_detail,
            'total_detections': int(len(det['labels'])),
            'detection_details': detection_details,
            'detected_texts': detected_texts[:50],
            'overlay_path': overlay_path,
        }

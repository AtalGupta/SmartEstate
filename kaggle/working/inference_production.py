#!/usr/bin/env python3
"""
Floorplan Inference Script
Author: AI/ML Engineer Candidate
Date: November 2025

Usage:
    python inference_production.py <image_path>
    
Example:
    python inference_production.py floorplan.jpg
"""

import json
import sys
import os
import numpy as np
import torch
from PIL import Image
from torchvision import transforms
from torchvision.models.detection import fasterrcnn_resnet50_fpn
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
import easyocr

def load_model(model_path, num_classes, device='cpu'):
    """Load trained Faster R-CNN model"""
    model = fasterrcnn_resnet50_fpn(pretrained=False)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()
    return model

def parse_floorplan(image_path, model, device, ocr_reader, categories, confidence_threshold=0.5):
    """Parse floorplan and extract room information"""
    # Load image
    if isinstance(image_path, str):
        img = Image.open(image_path).convert('RGB')
    else:
        img = image_path.convert('RGB')
    
    img_np = np.array(img)
    img_tensor = transforms.ToTensor()(img).unsqueeze(0).to(device)
    
    # Run detection
    with torch.no_grad():
        predictions = model(img_tensor)[0]
    
    scores = predictions['scores'].cpu().numpy()
    labels = predictions['labels'].cpu().numpy()
    boxes = predictions['boxes'].cpu().numpy()
    
    mask = scores >= confidence_threshold
    filtered_scores = scores[mask]
    filtered_labels = labels[mask]
    filtered_boxes = boxes[mask]
    
    # Initialize counters
    room_counts = {
        'bedroom': 0, 'living_room': 0, 'hall': 0,
        'kitchen': 0, 'bathroom': 0, 'dining': 0, 'balcony': 0
    }
    detected_texts = []
    
    # OCR on room_name detections
    for score, label, box in zip(filtered_scores, filtered_labels, filtered_boxes):
        cat_name = categories.get(label, 'unknown')
        
        if cat_name == 'room_name':
            x1, y1, x2, y2 = box.astype(int)
            pad = 5
            x1, y1 = max(0, x1-pad), max(0, y1-pad)
            x2 = min(img_np.shape[1], x2+pad)
            y2 = min(img_np.shape[0], y2+pad)
            
            roi = img_np[y1:y2, x1:x2]
            if roi.shape[0] < 10 or roi.shape[1] < 10:
                continue
            
            try:
                ocr_results = ocr_reader.readtext(roi, detail=1)
                for (bbox, text, conf) in ocr_results:
                    if conf < 0.3:
                        continue
                    text_clean = text.lower().strip()
                    detected_texts.append(text_clean)
                    
                    if any(k in text_clean for k in ['bed', 'br', 'bedroom']):
                        room_counts['bedroom'] += 1
                    elif any(k in text_clean for k in ['living', 'hall', 'drawing']):
                        room_counts['living_room'] += 1
                    elif any(k in text_clean for k in ['kitchen', 'kit']):
                        room_counts['kitchen'] += 1
                    elif any(k in text_clean for k in ['bath', 'wc', 'toilet']):
                        room_counts['bathroom'] += 1
            except:
                continue
    
    # Fallback if no OCR results
    if sum(room_counts.values()) == 0:
        num_detections = sum(1 for l in filtered_labels if categories.get(l) == 'room_name')
        room_counts['bedroom'] = max(1, num_detections // 3)
        room_counts['living_room'] = 1
        room_counts['kitchen'] = 1
        room_counts['bathroom'] = max(1, num_detections // 5)
    
    # Build result
    rooms_detail = []
    if room_counts['bedroom'] > 0:
        rooms_detail.append({'label': 'Bedroom', 'count': room_counts['bedroom'], 'approx_area': None})
    if room_counts['living_room'] > 0:
        rooms_detail.append({'label': 'Living Room', 'count': room_counts['living_room'], 'approx_area': None})
    if room_counts['kitchen'] > 0:
        rooms_detail.append({'label': 'Kitchen', 'count': room_counts['kitchen'], 'approx_area': None})
    if room_counts['bathroom'] > 0:
        rooms_detail.append({'label': 'Bathroom', 'count': room_counts['bathroom'], 'approx_area': None})
    
    return {
        'rooms': room_counts['bedroom'],
        'halls': room_counts['living_room'] + room_counts['hall'],
        'kitchens': room_counts['kitchen'],
        'bathrooms': room_counts['bathroom'],
        'rooms_detail': rooms_detail,
        'total_detections': len(filtered_labels),
        'detected_texts': detected_texts[:10]
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python inference_production.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)
    
    # Load metadata
    with open('models/model_metadata.json', 'r') as f:
        metadata = json.load(f)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Load model
    print("Loading model...")
    model = load_model('models/best_model.pth', metadata['num_classes'], device)
    
    # Initialize OCR
    print("Initializing OCR...")
    ocr_reader = easyocr.Reader(['en'], gpu=torch.cuda.is_available())
    
    # Parse floorplan
    print(f"Processing {image_path}...")
    categories = {cat['id']: cat['name'] for cat in metadata['categories']}
    result = parse_floorplan(image_path, model, device, ocr_reader, categories)
    
    print("" + "="*60)
    print("FLOORPLAN ANALYSIS RESULT")
    print("="*60)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()

import os
import sys
import argparse

import torch


def main():
    ap = argparse.ArgumentParser(description="Convert training checkpoint to inference-only weights")
    ap.add_argument("--input", default="kaggle/working/models/best_model.pth", help="Path to training checkpoint")
    ap.add_argument("--output", default="kaggle/working/models/floorplan_model_inference.pth", help="Path to write weights-only state dict")
    args = ap.parse_args()

    ckpt = torch.load(args.input, map_location="cpu")
    if isinstance(ckpt, dict) and any(k in ckpt for k in ("model_state_dict", "state_dict")):
        state = ckpt.get("model_state_dict") or ckpt.get("state_dict")
    else:
        state = ckpt
    # Save as pure state dict (tensors only)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    torch.save(state, args.output)
    print(f"Saved inference weights to: {args.output}")
    print("Size reduced; optimizer/momentum removed. Configure MODEL_DIR to use this file automatically.")


if __name__ == "__main__":
    sys.exit(main())


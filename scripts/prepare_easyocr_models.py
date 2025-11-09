import os
import sys

REQUIRED_FILES = [
    "craft_mlt_25k.pth",  # detector
    "english_g2.pth",     # recognizer for English
]


def main():
    model_dir = os.environ.get("OCR_MODEL_DIR", "models/easyocr")
    os.makedirs(model_dir, exist_ok=True)
    print(f"Checking EasyOCR model directory: {model_dir}")
    missing = []
    for f in REQUIRED_FILES:
        p = os.path.join(model_dir, f)
        if not os.path.exists(p):
            missing.append(f)
    if not missing:
        print("All required EasyOCR weights are present.")
        return 0
    print("Missing files:")
    for f in missing:
        print(" -", f)
    print("\nOptions to resolve:")
    print("1) Online bootstrap (once):\n   - Run any OCR call (Phase 1 parse), EasyOCR will download missing weights into:")
    print("     ", model_dir)
    print("2) Offline copy (recommended for CI/offline):\n   - Download these files from EasyOCR releases on a machine with internet:")
    print("     - craft_mlt_25k.pth (detector)")
    print("     - english_g2.pth (recognizer)")
    print("   - Place them into:")
    print("     ", model_dir)
    print("   - Re-run this script to verify.")
    return 1


if __name__ == "__main__":
    sys.exit(main())


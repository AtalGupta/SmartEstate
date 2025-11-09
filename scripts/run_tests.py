#!/usr/bin/env python
"""
Unified test runner for SmartEstate.

Usage:
    uv run python scripts/run_tests.py
    uv run python scripts/run_tests.py --integration
    uv run python scripts/run_tests.py --suite tests/test_phase1.py --suite tests/phase3
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITES = [
    "tests/test_phase1.py",
    "tests/test_phase2_utils.py",
    "tests/phase3",
]
INTEGRATION_SUITE = "tests/test_phase2_smoke.py"
REQUIRED_IMPORTS = (
    "pydantic",
    "fastapi",
    "sqlalchemy",
    "torch",
    "langchain",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SmartEstate test runner")
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Include integration smoke tests (requires Postgres, Elasticsearch, and Ollama).",
    )
    parser.add_argument(
        "--suite",
        action="append",
        help="Custom pytest target(s). Overrides default suites if provided.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose pytest output (passes -vv).",
    )
    parser.add_argument(
        "--fail-fast",
        "-x",
        action="store_true",
        help="Stop on first failure (passes -x).",
    )
    return parser.parse_args()


def ensure_pytest() -> None:
    if shutil.which("pytest"):
        return
    try:
        import pytest  # noqa: F401
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "pytest is not available. Install dependencies via `uv sync` or `pip install -r requirements.txt`."
        ) from exc


def ensure_project_dependencies() -> None:
    missing: List[str] = []
    for module in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module)
        except Exception:
            missing.append(module)
    if missing:
        formatted = ", ".join(missing)
        raise SystemExit(
            f"Missing runtime dependencies: {formatted}. "
            "Run `uv sync` (preferred) or `pip install -r requirements.txt` before executing tests."
        )


def warn_missing_assets() -> None:
    assets_excel = ROOT / "assets" / "Property_list.xlsx"
    if not assets_excel.exists():
        print(f"[warn] Expected sample Excel at {assets_excel} (some tests will skip).")
    images_dir = ROOT / "assets" / "images"
    if not images_dir.is_dir():
        print(f"[warn] Expected sample images directory at {images_dir} (Phase 1 smoke test may skip).")
    easyocr_dir = ROOT / "models" / "easyocr"
    if not easyocr_dir.is_dir():
        print(f"[warn] EasyOCR model directory missing at {easyocr_dir} (create it or run prepare_easyocr_models.py).")


def build_pytest_command(args: argparse.Namespace, suites: List[str]) -> List[str]:
    cmd = [sys.executable, "-m", "pytest"]
    if args.verbose:
        cmd.append("-vv")
    else:
        cmd.append("-q")
    if args.fail_fast:
        cmd.append("-x")
    cmd.extend(suites)
    return cmd


def main() -> int:
    args = parse_args()
    ensure_pytest()
    ensure_project_dependencies()
    warn_missing_assets()

    suites = args.suite[:] if args.suite else DEFAULT_SUITES[:]
    env = os.environ.copy()
    if args.integration:
        env["RUN_PHASE2_SMOKE_TEST"] = "1"
        if INTEGRATION_SUITE not in suites:
            suites.append(INTEGRATION_SUITE)

    cmd = build_pytest_command(args, suites)
    print(f"[info] Running pytest: {' '.join(cmd)}")
    if args.integration and env.get("RUN_PHASE2_SMOKE_TEST") != "1":
        env["RUN_PHASE2_SMOKE_TEST"] = "1"
    result = subprocess.run(cmd, cwd=ROOT, env=env)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

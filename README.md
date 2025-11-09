# SmartEstate – End-to-End Real Estate Search Engine

An industry-style implementation of the SmartSense AI/ML-II case study covering:

1. **Phase 1:** Floorplan CV + OCR (Faster R-CNN + EasyOCR) → structured JSON + overlays. 
2. **Phase 2:** ETL + storage (PostgreSQL JSONB + Elasticsearch + certificate text). 
3. **Phase 3:** LangGraph agents (router, planner, recall, SQL, RAG, renovation, report) backed by multi-layer memory and an Ollama LLM. 
4. **Phase 4:** FastAPI backend + Streamlit UI + Docker Compose deployment (db, es, ollama, api, ui).

![System Architecture](docs/System_Architecture.png)

---

## Repository Layout

```
SmartEstate/
├── api/                     # FastAPI endpoints (Phase 4)
├── phase3/                  # LangGraph graph + nodes + prompts
├── smartestate/             # Shared modules (config, DB, ES, parser wrappers)
├── scripts/                 # ETL, OCR prep, checkpoint conversion, ingest CLI
├── streamlit_app.py & pages # Streamlit UI (ingest, floorplan, chat)
├── kaggle/working/          # Phase 1 notebook, weights, outputs, inference script
├── assets/                  # Dataset assets (Excel, images)
├── docker-compose.yml       # Full stack (db, es, ollama, api, ui)
├── pyproject.toml / uv.lock # Dependency lock (uv)
├── requirements.txt         # pip-friendly dependency list
├── README_PHASE1.md         # Phase 1 data split/training summary
└── docs/                    # System diagram, PPT placeholder, etc.
```

Artifacts required for submission are under version control (`kaggle/working/` for CV weights, `scripts/` for ETL, `api/` + `streamlit_app.py` for backend/UI).

---

## Quick Start

```bash
# Install dependencies (uv preferred)
# Install uv (once) if you don't already have it:
Linux/macOS: curl -LsSf https://astral.sh/uv/install.sh | sh

Windows (PowerShell): powershell -c "irm https://astral.sh/uv/install.ps1 | more"

uv venv # create virtual environment

uv sync # auto sync dependencies from .toml file to venv 

# Ensure OCR weights exist
uv run python scripts/prepare_easyocr_models.py

uv pip freeze > requirements.txt ## keep requirements.txt updated

# Install from requirements.txt
uv pip install -r requirements.txt
```

### Docker (recommended deployment)
```bash
# Pull Llama 3.1 weights into the bundled Ollama service
docker compose run --rm ollama ollama pull llama3.1:8b

# Bring up db + es + ollama + api + ui
docker compose up -d db es ollama api ui

# UI available at http://localhost:8501
```

### Manual run
1. Start Postgres + Elasticsearch (e.g., `docker compose up -d db es`).
2. Run Ollama locally and pull the model (`ollama pull llama3.1:8b`).
3. API: `uv run uvicorn api.main:app --host 0.0.0.0 --port 8000`.
4. UI: `uv run streamlit run streamlit_app.py`.

---

## Phase Highlights

| Phase | Key Decisions |
| --- | --- |
| **1 – CV & OCR** | Faster R-CNN (ResNet50-FPN) + EasyOCR with domain heuristics; overlay output stored under `outputs/overlays/`; artifacts live in `kaggle/working/`. |
| **2 – ETL & Storage** | `scripts/ingest.py` ingests Excel → runs Phase 1 parser → stores canonical JSONB rows + parsed JSON in Postgres; text and certificates indexed in Elasticsearch with MiniLM embeddings. |
| **3 – Agents** | LangGraph orchestrates router, planner, recall, SQL, RAG, renovation, and report nodes with multi-layer memory (conversations, user profile, semantic). Ollama (Llama 3.1) produces grounded summaries. |
| **4 – API & UI** | FastAPI exposes `/ingest`, `/parse-floorplan`, `/chat` (REST + WS), `/report`; Streamlit UI has ingest/floorplan/chat tabs; Docker Compose bundles db/es/ollama/api/ui. |

---

## Demo Flow

1. **Ingest** – UI → 📥 Ingest → upload `assets/Property_list.xlsx` → ETL summary shown (rows ingested/indexed).  
2. **Floorplan Parse** – UI → 📐 Floorplan → upload any `assets/images/*.jpg` → view structured JSON + overlay path.  
3. **Chatbot** – UI → 💬 Chat:
   - “I am looking in Hyderabad under 70L, 2BHK.” (planner extracts preferences)
   - “Find options.” (SQL agent applies memory, returns shortlist via Ollama)
   - “What fire safety certificates are available in Hyderabad?” (RAG over certificate PDFs with citations)
   - “Estimate renovation for PROP-10001.”
   - Click “Generate Report” for PDF summary.

All answers cite property IDs and originate from either Postgres (structured) or Elasticsearch (certificate/text) per JD requirements.

---

## Testing

```bash
# Default unit suites (Phase 1/2 utils + Phase 3 graph components)
uv run python scripts/run_tests.py

# Include integration smoke test (requires Postgres + Elasticsearch + Ollama)
uv run python scripts/run_tests.py --integration
```

Under the hood this runs the existing pytest suites that cover the Phase 1 parser smoke test, ETL utilities, and LangGraph router/planner/memory helpers. The script verifies project dependencies up front and will prompt you to run `uv sync` if anything is missing. Pass `--suite path/to/test.py` to target a specific file or folder, and `-v`/`-x` to change verbosity or stop on first failure.

---


## Notes

- `requirements.txt` mirrors `pyproject.toml` for environments without uv.
- OCR weights live under `models/easyocr/` (checked via `scripts/prepare_easyocr_models.py`).
- System architecture diagram (`docs/system_architecture.png`) is generated via the helper script shown later in this README (see docs/notes if regenerating).

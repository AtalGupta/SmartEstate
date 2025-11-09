# SmartEstate Setup Guide

This guide walks through everything required to bring SmartEstate online on Windows, macOS, or Linux. Work through the phases sequentially; each ends with a quick verification step so you always know the stack is healthy before moving on.

---

## 1. Prerequisites

| Tool | Version | Install or verify |
| --- | --- | --- |
| Git | >= 2.35 | `git --version` |
| Python | 3.11.x | macOS/Linux: `python3 --version` / Windows: `py --version` |
| pip + uv | latest | `pip install --upgrade pip uv` |
| Docker Engine + Compose | >= 24.x / Compose v2 | macOS/Windows: Docker Desktop / Linux: distro packages (`docker --version`, `docker compose version`) |
| Optional GPU drivers | CUDA 12+ if you plan to retrain CV models | Install vendor drivers |

Tip: run commands from PowerShell on Windows and from bash/zsh on macOS or Linux.

---

## 2. Clone the repository

```bash
git clone https://github.com/<your-org>/SmartEstate.git
cd SmartEstate
```

Already cloned? make sure you are current:

```bash
git fetch origin
git checkout main
git pull --ff-only
```

---

## 3. Python environment and dependencies

### macOS or Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip uv
uv sync
```

### Windows (PowerShell)
```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip uv
uv sync
```

If uv is not available, fall back to:

```bash
pip install -r requirements.txt
```

Smoke test the environment:

```bash
uv run python -c "import fastapi, torch, streamlit; print('Env OK')"
```

---

## 4. Environment variables

1. Copy the sample file:
   ```bash
   cp .env.example .env        # macOS/Linux
   copy .env.example .env      # Windows
   ```
2. Adjust values if needed:
   - `DATABASE_URL` defaults to a local Postgres instance.
   - `ELASTICSEARCH_URL` defaults to `http://localhost:9200`.
   - `ELASTICSEARCH_INDEX` defaults to `properties`.
   - `MODEL_DIR` points to the Kaggle Phase 1 artifacts (`kaggle/working`).
   - `OCR_MODEL_DIR` stores EasyOCR weights (`models/easyocr`).
   - `EMBEDDING_MODEL` can be any sentence-transformers model reachable offline or online.

Verify the app reads your settings:

```bash
uv run python -c "from smartestate.config import get_settings; print(get_settings().model_dump())"
```

---

## 5. Assets and model weights

1. **Floorplan model**  
   - Check that `kaggle/working/models` contains the `.pth` files referenced by the Phase 1 notebook.  
   - Optional conversion for faster inference:
     ```bash
     uv run python scripts/convert_checkpoint_to_inference.py \
       --input kaggle/working/models/best_model.pth \
       --output kaggle/working/models/floorplan_model_inference.pth
     ```

2. **EasyOCR weights**  
   - Confirm the detector (`craft_mlt_25k.pth`) and recognizer (`english_g2.pth`) exist under `models/easyocr`:
     ```bash
     uv run python scripts/prepare_easyocr_models.py
     ```
   - If the script reports missing files, download them once from EasyOCR releases and place them in the directory above.

3. **Sample data**  
   - `assets/Property_list.xlsx` feeds the ETL script.  
   - `assets/images/*.jpg` provides sample floorplans for OCR validation.

---

## 6. Manual (local) runtime

### 6.1 Start backing services

Option A - use Docker for infrastructure only:
```bash
docker compose up -d db es ollama
docker compose run --rm ollama ollama pull llama3.1:8b
```

Option B - services on the host:
```bash
pg_ctl start          # or brew services start postgresql
elasticsearch &       # ensure it listens on 9200
ollama serve &
ollama pull llama3.1:8b
```

Check connectivity:
```bash
pg_isready -h localhost -p 5432
curl http://localhost:9200
curl http://localhost:11434/api/tags
```

### 6.2 Ingest sample data

```bash
uv run python scripts/ingest.py --file assets/Property_list.xlsx
```

You should see counts for Postgres rows inserted and Elasticsearch documents indexed.

### 6.3 Start backend and UI

```bash
# API
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# UI (new shell)
uv run streamlit run streamlit_app.py --server.port 8501
```

Validate:
```bash
curl http://localhost:8000/health
open http://localhost:8501      # macOS
start http://localhost:8501     # Windows
```

---

## 7. Full Docker Compose deployment

1. Ensure `.env` exists in the project root (Docker automatically loads it for the `api` service).
2. Build images:
   ```bash
   docker compose build
   ```
3. Pre-pull the Ollama model inside its service volume:
   ```bash
   docker compose run --rm ollama ollama pull llama3.1:8b
   ```
4. Launch the entire stack:
   ```bash
   docker compose up -d db es ollama api ui
   ```
5. Tail logs if needed:
   ```bash
   docker compose logs -f api
   docker compose logs -f ui
   ```
6. Smoke tests:
   - API: `curl http://localhost:8000/health`
   - UI: browse to `http://localhost:8501`
   - Elasticsearch: `curl http://localhost:9200/_cat/indices`

Stop services:
```bash
docker compose down          # keep data volumes
docker compose down -v       # remove db/es/ollama volumes
```

---

## 8. Tests and linting

```bash
# Default Phase 1/2 utility + Phase 3 suites
uv run python scripts/run_tests.py
```

Integration smoke (requires Postgres, Elasticsearch, and Ollama):

```bash
uv run python scripts/run_tests.py --integration
```

Target individual suites when iterating:

```bash
uv run python scripts/run_tests.py --suite tests/test_phase1.py
uv run python scripts/run_tests.py --suite tests/phase3 --verbose
```

---

## 9. Troubleshooting quick reference

| Symptom | Fix |
| --- | --- |
| `psycopg.OperationalError` when starting the API | Verify Postgres is running and `DATABASE_URL` matches (`docker compose ps db`). |
| `ConnectionError` to Elasticsearch | Review `docker compose logs es`; recreate the volume if it refuses to start (`docker compose down -v es`). |
| Ollama refuses connections | Model not pulled; rerun `docker compose run --rm ollama ollama pull llama3.1:8b`. |
| Missing EasyOCR weights | Re-run `uv run python scripts/prepare_easyocr_models.py` and copy the requested `.pth` files. |
| LangGraph node errors at startup | Run `uv sync --reinstall` and confirm `phase3` assets exist. |
| Streamlit cannot reach the API in Docker | The UI points to `http://host.docker.internal:8000`; ensure Docker Desktop >= 4.24 or add an `extra_hosts` entry with your host IP on Linux. |

---

## 10. Next steps

1. Keep `.env` local unless you intentionally scrub secrets.
2. Use `/ingest` or `scripts/ingest.py` with your own Excel files to populate the database.
3. When you modify FastAPI or LangGraph code, rebuild the API image (`docker compose build api && docker compose up -d api`) or restart the local process.

You now have a dependable, platform-agnostic recipe for cloning, configuring, and running SmartEstate in local developer mode or via Docker Compose.


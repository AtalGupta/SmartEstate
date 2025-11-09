import os
import pytest


@pytest.mark.skipif(os.environ.get("RUN_PHASE2_SMOKE_TEST") != "1", reason="Set RUN_PHASE2_SMOKE_TEST=1 to run integration smoke test")
def test_ingest_excel_smoke():
    try:
        from smartestate.etl import ingest_excel
    except Exception as e:
        pytest.skip(f"Phase 2 dependencies not available: {e}")
    # Requires running Postgres + ES as configured in .env or docker-compose
    excel = os.path.join("assets", "Property_list.xlsx")
    if not os.path.exists(excel):
        pytest.skip("Excel file not found")
    res = ingest_excel(excel)
    assert set(["ingested_rows", "failed_rows", "indexed_docs", "skipped_index"]) <= set(res.keys())

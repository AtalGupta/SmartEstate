from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile

from smartestate.config import get_settings
from smartestate.db import init_db
from smartestate.es_client import ensure_index
from smartestate.etl import ingest_excel
from smartestate.floorplan import FloorplanParser
from phase3.graph.build_graph import build_graph
from phase3.graph.state import GraphState, Message
from smartestate.tools.memory import (
    get_or_create_conversation,
    add_message,
    load_user_memory,
    update_user_memory,
    add_semantic_memory,
)


app = FastAPI(title="SmartEstate API", version="0.1.0")

# Allow Streamlit frontend and local dev to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    try:
        init_db()
    except Exception as e:
        print(f"[startup] DB init failed: {e}")
    try:
        ensure_index()
    except Exception as e:
        print(f"[startup] ES index ensure failed: {e}")
    try:
        app.state.graph = build_graph()
    except Exception as e:
        print(f"[startup] Graph build failed: {e}")


@app.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "database_url": settings.database_url,
        "elasticsearch_url": settings.elasticsearch_url,
        "elasticsearch_index": settings.elasticsearch_index,
    }


@app.post("/ingest")
async def ingest(file: UploadFile = File(None), path: str = Form(None)):
    if file is None and not path:
        return JSONResponse({"error": "Provide either uploaded file or 'path'"}, status_code=400)
    if file is not None:
        fd, tmp = tempfile.mkstemp(prefix="smartestate_excel_", suffix=os.path.splitext(file.filename or "")[1] or ".xlsx")
        os.close(fd)
        with open(tmp, "wb") as f:
            f.write(await file.read())
        result = ingest_excel(tmp)
        os.remove(tmp)
        return result
    result = ingest_excel(path)
    return result


@app.post("/parse_floorplan")
async def parse_floorplan(file: UploadFile = File(None), path: str = Form(None)):
    if file is None and not path:
        return JSONResponse({"error": "Provide either uploaded image or 'path'"}, status_code=400)
    parser = FloorplanParser()
    if file is not None:
        fd, tmp = tempfile.mkstemp(prefix="smartestate_image_", suffix=os.path.splitext(file.filename or "")[1] or ".jpg")
        os.close(fd)
        with open(tmp, "wb") as f:
            f.write(await file.read())
        try:
            result = parser.parse(tmp)
        finally:
            os.remove(tmp)
        return result
    return parser.parse(path)


@app.post("/chat")
def chat(message: str, user_id: str = "demo-user"):
    graph = getattr(app.state, "graph", None)
    if graph is None:
        graph = build_graph()
    # Memory: load profile and add semantic memory for message
    conv_id = get_or_create_conversation(user_id)
    add_message(conv_id, "user", message)
    try:
        add_semantic_memory(user_id, message)
    except Exception:
        pass
    user_mem = load_user_memory(user_id)
    state = GraphState(messages=[Message(role="user", content=message)], context={"memory": user_mem, "user_id": user_id})
    out = graph.invoke(state)
    # LangGraph returns a dict, not a GraphState object
    if isinstance(out, dict):
        intent = out.get("intent", "unknown")
        result_obj = out.get("result")
        context = out.get("context", {})
    else:
        intent = getattr(out, "intent", "unknown")
        result_obj = getattr(out, "result", None)
        context = getattr(out, "context", {})

    res = result_obj.dict() if result_obj and hasattr(result_obj, "dict") else (result_obj if isinstance(result_obj, dict) else {})
    # For PDF, return a flag and omit raw bytes in JSON
    if res.get("data", {}).get("pdf"):
        res["data"]["pdf"] = "<bytes>"
    # Update memory with any planner-extracted prefs
    mem_updates = context.get("memory") if context else None
    if mem_updates:
        try:
            update_user_memory(user_id, mem_updates)
        except Exception:
            pass
    add_message(conv_id, "assistant", res.get("text", ""))
    return {"intent": intent, "result": res, "memory": mem_updates or user_mem}


@app.post("/report")
def report(summary_hint: str = Form(None)):
    import os
    from datetime import datetime
    from smartestate.tools.pdf import generate_summary_pdf
    from smartestate.db import session_scope
    from smartestate.models import Property

    # Get recent properties to include in report
    with session_scope() as session:
        properties = session.query(Property).limit(10).all()
        sections = []
        if properties:
            lines = [f"{p.external_id} | {p.title} | {p.location} | ₹{p.price:,}" for p in properties]
            sections.append({"heading": "Recent Properties", "lines": lines})
        else:
            sections.append({"heading": "Summary", "lines": ["No properties available for report."]})

    # Generate PDF
    pdf_bytes = generate_summary_pdf("SmartEstate Property Report", sections)

    # Save PDF to disk
    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = f"outputs/report_{timestamp}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    return {
        "intent": "report",
        "result": {"text": f"PDF report generated with {len(properties)} properties", "data": {"pdf": "<bytes>", "pdf_path": pdf_path}},
        "pdf_path": pdf_path
    }


@app.websocket("/chat/ws")
async def chat_ws(ws: WebSocket):
    await ws.accept()
    graph = getattr(app.state, "graph", None)
    if graph is None:
        graph = build_graph()
    try:
        while True:
            data = await ws.receive_json()
            message = data.get("message", "")
            user_id = data.get("user_id", "demo-user")
            # Persist message + memory
            conv_id = get_or_create_conversation(user_id)
            add_message(conv_id, "user", message)
            try:
                add_semantic_memory(user_id, message)
            except Exception:
                pass
            user_mem = load_user_memory(user_id)
            state = GraphState(messages=[Message(role="user", content=message)], context={"memory": user_mem, "user_id": user_id})
            out = graph.invoke(state)
            # LangGraph returns a dict, not a GraphState object
            if isinstance(out, dict):
                intent = out.get("intent", "unknown")
                result_obj = out.get("result")
                context = out.get("context", {})
            else:
                intent = getattr(out, "intent", "unknown")
                result_obj = getattr(out, "result", None)
                context = getattr(out, "context", {})

            res = result_obj.dict() if result_obj and hasattr(result_obj, "dict") else (result_obj if isinstance(result_obj, dict) else {})
            if res.get("data", {}).get("pdf"):
                res["data"]["pdf"] = "<bytes>"
            mem_updates = context.get("memory") if context else None
            if mem_updates:
                try:
                    update_user_memory(user_id, mem_updates)
                except Exception:
                    pass
            add_message(conv_id, "assistant", res.get("text", ""))
            await ws.send_json({"intent": intent, "result": res, "memory": mem_updates or user_mem})
    except WebSocketDisconnect:
        return

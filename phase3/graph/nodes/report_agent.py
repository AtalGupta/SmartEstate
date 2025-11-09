from typing import List, Dict, Any

from ..state import GraphState, AgentResult
from smartestate.tools.pdf import generate_summary_pdf


def report_node(state: GraphState) -> GraphState:
    # Use last SQL/RAG results if available
    sections: List[Dict[str, Any]] = []
    if state.result and state.result.data.get("rows"):
        rows = state.result.data["rows"]
        lines = [f"{r['external_id']} | {r['title']} | {r['location']} | ₹{r['price']:,}" for r in rows]
        sections.append({"heading": "Shortlist", "lines": lines})
    elif state.result and state.result.data.get("hits"):
        hits = state.result.data["hits"]
        lines = [f"{h.get('title','')} | {h.get('location','')} | ₹{h.get('price','')}" for h in hits]
        sections.append({"heading": "Relevant Properties", "lines": lines})
    else:
        sections.append({"heading": "Summary", "lines": ["No data to summarize."]})

    pdf_bytes = generate_summary_pdf("SmartEstate Report", sections)
    state.result = AgentResult(text="Generated PDF report (bytes)", data={"pdf": pdf_bytes})
    return state

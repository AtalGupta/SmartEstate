import json
from langchain_core.prompts import ChatPromptTemplate

from ..state import GraphState, AgentResult, Citation
from ..prompts import RAG_SUMMARY_PROMPT
from smartestate.tools.search import search_properties
from smartestate.tools.llm_provider import get_llm


def rag_node(state: GraphState) -> GraphState:
    query = state.messages[-1].content if state.messages else ""
    q_lower = query.lower()
    needs_certificate = any(keyword in q_lower for keyword in [
        "certificate", "certification", "inspection", "compliance", "fire", "safety", "report"
    ])

    hits = search_properties(query, k=5, needs_certificate=needs_certificate)
    llm = get_llm()
    cits = [Citation(source_id=str(h.get("id", "")), snippet=(h.get("full_text") or h.get("long_description") or "")[:200]) for h in hits]

    if llm and hits:
        condensed_hits = []
        for h in hits:
            condensed_hits.append({
                "property_id": h.get("id"),
                "title": h.get("title"),
                "location": h.get("location"),
                "price": h.get("price"),
                "cert_links": h.get("cert_links"),
                "snippet": (h.get("full_text") or h.get("long_description") or "")[:800],
            })
        prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_SUMMARY_PROMPT),
            ("human", "Question: {question}\nDocs:```json\n{docs}\n```"),
        ])
        msgs = prompt.format_messages(question=query, docs=json.dumps(condensed_hits, ensure_ascii=False))
        response = llm.invoke(msgs)
        answer = response.content if hasattr(response, "content") else str(response)
    elif hits:
        answer_lines = []
        for h in hits:
            line = f"- {h.get('title','(no title)')} ({h.get('id')})"
            if needs_certificate:
                certs = (h.get("cert_links") or {}).get("links") if isinstance(h.get("cert_links"), dict) else h.get("cert_links")
                if certs:
                    line += f" — certificates: {', '.join(certs[:3])}"
            answer_lines.append(line)
        answer = f"Found {len(hits)} relevant properties:\n" + "\n".join(answer_lines)
    else:
        answer = "No matching documents in the knowledge base."

    state.result = AgentResult(text=answer, data={"hits": hits}, citations=cits)
    return state

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from config import REPORT_TOP_K
from rag.store import search_session


@tool
def search_medical_report(
    query: str,
    session_id: Annotated[str, InjectedState("session_id")],
) -> str:
    """Search the user's uploaded medical report.

    Use this for their labs, findings, medications, imaging, or history.
    Results are passages from the indexed report, not general medical knowledge.
    """
    if not session_id:
        return "No session is available, so the report cannot be searched."
    hits = search_session(session_id, query, REPORT_TOP_K)
    if not hits:
        return (
            "No medical report is indexed for this session, "
            "or nothing in the report matched that search."
        )
    parts = []
    for index, hit in enumerate(hits, start=1):
        metadata = hit["metadata"]
        source = metadata.get("source", "report")
        page = metadata.get("page", "?")
        parts.append(f"[{index}] {source} page {page}\n{hit['text']}")
    return "\n\n".join(parts)

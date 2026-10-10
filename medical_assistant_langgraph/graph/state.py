from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    symptoms: str
    symptom_questions_asked: int
    report_indexed: bool
    pending_report_path: str | None
    session_id: str
    needs_personal_report: bool
    symptoms_sufficient: bool
    red_flag: bool
    ingest_note: str
    calls: list
    input_decision: str

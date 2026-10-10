import json
import re

from langchain_core.messages import AIMessage, SystemMessage
from pydantic import BaseModel, Field

from config import DISCLAIMER, MAX_SYMPTOM_QUESTIONS, URGENT_CARE
from graph.prompts import ANSWER_SYSTEM, ASK_SYMPTOMS_SYSTEM, UNDERSTAND_SYSTEM
from graph.state import AgentState
from graph.usage import append_call, call_record, timed_invoke, with_turn_metadata
from llm import get_llm
from rag.ingest import ingest_report
from tools.document_search import search_medical_report
from tools.web_search import search_web

TOOLS = [search_medical_report, search_web]


class Understanding(BaseModel):
    symptoms: str = Field(
        description="Rolling summary of the user's symptoms and concerns. Empty if none."
    )
    symptoms_sufficient: bool = Field(
        description="True for a general question, or when a personal concern includes duration, severity, or context."
    )
    needs_personal_report: bool = Field(
        description="True when the user is asking about their own report, labs, results, or history."
    )
    red_flag: bool = Field(
        description="True for chest pain, trouble breathing, stroke signs, or severe bleeding."
    )


def message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
        return "".join(parts)
    return str(content)


def finish_text(text: str, state: AgentState) -> str:
    body = (text or "").strip()
    parts = []
    if state.get("red_flag") and "emergency care" not in body.lower():
        parts.append(URGENT_CARE)
    if body:
        parts.append(body)
    if DISCLAIMER not in body:
        parts.append(DISCLAIMER)
    return "\n\n".join(parts)


def _parse_understanding(payload) -> Understanding:
    if isinstance(payload, Understanding):
        return payload
    if isinstance(payload, dict):
        return Understanding.model_validate(payload)
    raw = message_text(getattr(payload, "content", payload))
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError("The model did not return symptom details.")
    return Understanding.model_validate(json.loads(match.group(0)))


def understand(state: AgentState) -> dict:
    system = UNDERSTAND_SYSTEM.format(symptoms=state.get("symptoms") or "None yet.")
    messages = [SystemMessage(content=system), *state.get("messages", [])]
    structured = get_llm().with_structured_output(Understanding, include_raw=True)
    calls: list[dict] = list(state.get("calls") or [])
    try:
        result, record = timed_invoke(structured, messages, "understand")
        if isinstance(result, dict):
            raw = result.get("raw")
            if raw is not None:
                calls.append(call_record(raw, "understand", record["latency_ms"]))
            else:
                calls.append(record)
            if result.get("parsing_error"):
                raise result["parsing_error"]
            parsed = _parse_understanding(result.get("parsed"))
        else:
            parsed = _parse_understanding(result)
            calls.append(record)
    except Exception:
        raw, record = timed_invoke(
            get_llm(),
            [
                SystemMessage(
                    content=system
                    + "\nReply with a JSON object containing symptoms, symptoms_sufficient, "
                    "needs_personal_report, and red_flag."
                ),
                *state.get("messages", []),
            ],
            "understand",
        )
        calls.append(record)
        parsed = _parse_understanding(raw)

    return {
        "symptoms": parsed.symptoms.strip(),
        "symptoms_sufficient": parsed.symptoms_sufficient,
        "needs_personal_report": parsed.needs_personal_report,
        "red_flag": parsed.red_flag,
        "calls": calls,
    }


def route_after_understand(state: AgentState) -> str:
    if state.get("pending_report_path"):
        return "ingest"
    asked = state.get("symptom_questions_asked") or 0
    if not state.get("symptoms_sufficient") and asked < MAX_SYMPTOM_QUESTIONS:
        return "ask_symptoms"
    if state.get("needs_personal_report") and not state.get("report_indexed"):
        return "ask_report"
    return "answer"


def ask_symptoms(state: AgentState) -> dict:
    system = ASK_SYMPTOMS_SYSTEM.format(
        symptoms=state.get("symptoms") or "None yet.",
        red_flag=bool(state.get("red_flag")),
        urgent=URGENT_CARE,
    )
    response, record = timed_invoke(
        get_llm(),
        [SystemMessage(content=system), *state.get("messages", [])],
        "ask_symptoms",
    )
    calls = append_call(state, record)
    return {
        "messages": [
            AIMessage(
                content=finish_text(message_text(response.content), state),
                response_metadata=with_turn_metadata(None, calls),
            )
        ],
        "symptom_questions_asked": (state.get("symptom_questions_asked") or 0) + 1,
        "calls": calls,
    }


def ask_report(state: AgentState) -> dict:
    summary = (state.get("symptoms") or "").strip()
    lead = f"I have this so far: {summary}\n\n" if summary else ""
    text = (
        f"{lead}To answer about your own results, upload a PDF or text report "
        "with the sidebar uploader. I will index it and use only what is in the file."
    )
    calls = list(state.get("calls") or [])
    return {
        "messages": [
            AIMessage(
                content=finish_text(text, state),
                response_metadata=with_turn_metadata(None, calls),
            )
        ]
    }


def ingest(state: AgentState) -> dict:
    path = state.get("pending_report_path") or ""
    session_id = state.get("session_id") or ""
    try:
        result = ingest_report(path, session_id)
    except Exception as exc:
        return {
            "pending_report_path": None,
            "ingest_note": f"Could not index the report: {exc}",
        }

    if result["chunks"] == 0:
        return {
            "pending_report_path": None,
            "report_indexed": False,
            "ingest_note": (
                f"{result['source']} had no extractable text. "
                "A scanned PDF without a text layer cannot be indexed."
            ),
        }

    return {
        "pending_report_path": None,
        "report_indexed": True,
        "ingest_note": f"Indexed {result['source']} ({result['chunks']} chunks).",
    }


def answer(state: AgentState) -> dict:
    system = ANSWER_SYSTEM.format(
        disclaimer=DISCLAIMER,
        urgent=URGENT_CARE,
        symptoms=state.get("symptoms") or "None yet.",
        report_indexed=bool(state.get("report_indexed")),
        ingest_note=state.get("ingest_note") or "None.",
        red_flag=bool(state.get("red_flag")),
    )
    response, record = timed_invoke(
        get_llm().bind_tools(TOOLS),
        [SystemMessage(content=system), *state.get("messages", [])],
        "answer",
    )
    if response.tool_calls:
        record["step"] = "answer (tool request)"
    calls = append_call(state, record)
    update: dict = {"messages": [response], "calls": calls}
    if not response.tool_calls:
        response.content = finish_text(message_text(response.content), state)
        response.response_metadata = with_turn_metadata(response.response_metadata, calls)
        update["ingest_note"] = ""
    return update


def route_after_answer(state: AgentState) -> str:
    last = state.get("messages", [])[-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "end"

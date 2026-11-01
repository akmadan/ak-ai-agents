"""HTTP server that follows the Agent Runtime container contract.

Agent Runtime sends POST requests with ``{"class_method": ..., "input": {...}}``
to ``/api/reasoning_engine`` (unary) and ``/api/stream_reasoning_engine``
(newline-delimited JSON). The container must listen on 0.0.0.0:8080.
"""

import base64
import json
import logging
import os
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, encoders, responses
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from config import UPLOADS_DIR
from graph.builder import get_graph
from graph.nodes import message_text
from rag.store import delete_session

ALLOWED_SUFFIXES = {".pdf", ".txt"}
NEW_SESSION_DEFAULTS = {
    "symptoms": "",
    "symptom_questions_asked": 0,
    "report_indexed": False,
    "needs_personal_report": False,
    "symptoms_sufficient": False,
    "red_flag": False,
    "ingest_note": "",
}

app = FastAPI()


class QueryRequest(BaseModel):
    class_method: str
    input: dict | None = None


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}, "recursion_limit": 20}


def _save_report(session_id: str, report: dict) -> str:
    name = Path(str(report.get("filename") or "")).name
    if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("report.filename must end in .pdf or .txt")
    data = base64.b64decode(report.get("content_base64") or "", validate=True)
    if not data:
        raise ValueError("report.content_base64 is empty")
    session_dir = UPLOADS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    destination = session_dir / name
    destination.write_bytes(data)
    return str(destination)


def _payload(message: str, session_id: str, report: dict | None) -> dict:
    payload = {"messages": [HumanMessage(content=message)], "session_id": session_id}
    if report:
        payload["pending_report_path"] = _save_report(session_id, report)
    if not get_graph().get_state(_config(session_id)).values:
        payload.update(NEW_SESSION_DEFAULTS)
    return payload


def _result(session_id: str) -> dict:
    values = get_graph().get_state(_config(session_id)).values or {}
    reply = ""
    turn = {}
    for message in reversed(values.get("messages") or []):
        if isinstance(message, AIMessage) and message.content and not message.tool_calls:
            reply = message_text(message.content)
            turn = (message.response_metadata or {}).get("turn") or {}
            break
    return {
        "session_id": session_id,
        "response": reply,
        "report_indexed": bool(values.get("report_indexed")),
        "symptoms": values.get("symptoms") or "",
        "turn": turn,
    }


class MedicalAssistant:
    def query(
        self,
        message: str,
        session_id: str | None = None,
        report: dict | None = None,
        **_: object,
    ) -> dict:
        session_id = session_id or str(uuid.uuid4())
        get_graph().invoke(_payload(message, session_id, report), config=_config(session_id))
        return _result(session_id)

    def stream_query(
        self,
        message: str,
        session_id: str | None = None,
        report: dict | None = None,
        **_: object,
    ):
        session_id = session_id or str(uuid.uuid4())
        payload = _payload(message, session_id, report)
        for update in get_graph().stream(
            payload, config=_config(session_id), stream_mode="updates"
        ):
            for node in update:
                yield {"session_id": session_id, "node": node}
        yield {"output": _result(session_id)}

    def delete_session(self, session_id: str, **_: object) -> dict:
        delete_session(session_id)
        return {"session_id": session_id, "deleted": True}


agent = MedicalAssistant()
UNARY_METHODS = {"query", "delete_session"}
STREAM_METHODS = {"stream_query"}


def _error(status: int, text: str) -> responses.JSONResponse:
    return responses.JSONResponse(status_code=status, content={"error": text})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/reasoning_engine")
async def query_endpoint(request: QueryRequest):
    if request.class_method not in UNARY_METHODS:
        return _error(400, f"Method {request.class_method} not found on agent")
    method = getattr(agent, request.class_method)
    try:
        output = await run_in_threadpool(method, **(request.input or {}))
    except (TypeError, ValueError) as exc:
        return _error(400, str(exc))
    return responses.JSONResponse(content=encoders.jsonable_encoder({"output": output}))


@app.post("/api/stream_reasoning_engine")
async def stream_query_endpoint(request: QueryRequest):
    if request.class_method not in STREAM_METHODS:
        return _error(400, f"Method {request.class_method} not found on agent")

    async def ndjson():
        try:
            chunks = agent.stream_query(**(request.input or {}))
            async for chunk in iterate_in_threadpool(chunks):
                yield json.dumps(encoders.jsonable_encoder(chunk)) + "\n"
        except Exception as exc:
            logging.exception("stream_query failed")
            yield json.dumps({"error": str(exc)}) + "\n"

    return responses.StreamingResponse(ndjson(), media_type="application/json")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

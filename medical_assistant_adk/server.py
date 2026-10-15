"""HTTP server that follows the Agent Runtime container contract.

Agent Runtime sends POST requests with ``{"class_method": ..., "input": {...}}``
to ``/api/reasoning_engine`` (unary) and ``/api/stream_reasoning_engine``
(newline-delimited JSON). The container must listen on 0.0.0.0:8080.
"""

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / "medical_assistant" / ".env")

import uvicorn
from fastapi import FastAPI, Request, encoders, responses
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from medical_assistant.agent import root_agent

APP_NAME = "medical_assistant"
DEFAULT_USER = "default"

app = FastAPI()
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)


class QueryRequest(BaseModel):
    class_method: str
    input: dict | None = None


async def _session_id(user_id: str, session_id: str | None) -> str:
    if session_id:
        existing = await session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        if existing:
            return session_id
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    return session.id


def _event_text(event) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "".join(p.text for p in event.content.parts if p.text and not p.thought)


async def _events(message: str, user_id: str, session_id: str):
    if not (message or "").strip():
        raise ValueError("message is required")
    content = types.Content(role="user", parts=[types.Part(text=message)])
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=content
    ):
        yield event


class MedicalAssistant:
    async def query(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str = DEFAULT_USER,
        **_: object,
    ) -> dict:
        session_id = await _session_id(user_id, session_id)
        reply = ""
        async for event in _events(message, user_id, session_id):
            if event.is_final_response():
                reply = _event_text(event) or reply
        return {"session_id": session_id, "user_id": user_id, "response": reply}

    async def stream_query(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str = DEFAULT_USER,
        **_: object,
    ):
        session_id = await _session_id(user_id, session_id)
        reply = ""
        async for event in _events(message, user_id, session_id):
            text = _event_text(event)
            if text:
                yield {"session_id": session_id, "author": event.author, "text": text}
            if event.is_final_response():
                reply = text or reply
        yield {"output": {"session_id": session_id, "user_id": user_id, "response": reply}}

    async def delete_session(
        self, session_id: str, user_id: str = DEFAULT_USER, **_: object
    ) -> dict:
        if not session_id:
            raise ValueError("session_id is required")
        await session_service.delete_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        return {"session_id": session_id, "deleted": True}


agent = MedicalAssistant()
UNARY_METHODS = {"query", "delete_session"}
STREAM_METHODS = {"stream_query", "async_stream_query"}


def _error(status: int, text: str) -> responses.JSONResponse:
    return responses.JSONResponse(status_code=status, content={"error": text})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


async def _parse(request: Request) -> QueryRequest:
    # Agent Runtime does not send Content-Type: application/json, so FastAPI
    # body binding sees a raw string. Decode the bytes ourselves.
    body = json.loads(await request.body() or b"{}")
    if isinstance(body, str):
        body = json.loads(body)
    return QueryRequest.model_validate(body)


@app.post("/api/reasoning_engine")
async def query_endpoint(request: Request):
    try:
        query = await _parse(request)
    except ValueError as exc:
        return _error(400, f"Invalid request body: {exc}")
    if query.class_method not in UNARY_METHODS:
        return _error(400, f"Method {query.class_method} not found on agent")
    method = getattr(agent, query.class_method)
    try:
        output = await method(**(query.input or {}))
    except (TypeError, ValueError) as exc:
        return _error(400, str(exc))
    return responses.JSONResponse(content=encoders.jsonable_encoder({"output": output}))


@app.post("/api/stream_reasoning_engine")
async def stream_query_endpoint(request: Request):
    try:
        query = await _parse(request)
    except ValueError as exc:
        return _error(400, f"Invalid request body: {exc}")
    if query.class_method not in STREAM_METHODS:
        return _error(400, f"Method {query.class_method} not found on agent")

    async def ndjson():
        try:
            async for chunk in agent.stream_query(**(query.input or {})):
                yield json.dumps(encoders.jsonable_encoder(chunk)) + "\n"
        except Exception as exc:
            logging.exception("stream_query failed")
            yield json.dumps({"error": str(exc)}) + "\n"

    return responses.StreamingResponse(ndjson(), media_type="application/json")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

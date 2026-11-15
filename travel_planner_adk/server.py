"""HTTP API for UI clients of the travel planner."""

import json
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / "travel_planner" / ".env")

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel
from pydantic import Field

from travel_planner.agent import root_agent
from travel_planner.cards import PlaceCard
from travel_planner.cards import cards_from_payload

logger = logging.getLogger("travel_planner.server")

APP_NAME = "travel_planner"
ROOT_AGENT = "travel_planner"
DEFAULT_USER = "default"

STATUS_BY_TOOL = {
    "destination_research": "Finding destinations",
    "itinerary_planning": "Planning the days",
    "budget_feasibility": "Checking the budget",
    "search_destinations": "Matching saved places",
    "search_web": "Searching the web",
}

app = FastAPI(title="Travel planner")
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)

_origins = os.getenv("CORS_ORIGINS", "*").strip()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _origins == "*" else [item.strip() for item in _origins.split(",") if item.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionCreate(BaseModel):
    user_id: str = DEFAULT_USER


class SessionCreated(BaseModel):
    session_id: str
    user_id: str


class ChatRequest(BaseModel):
    message: str
    user_id: str = DEFAULT_USER


class ChatResponse(BaseModel):
    session_id: str
    user_id: str
    reply: str
    cards: list[PlaceCard] = Field(default_factory=list)
    assumptions: str | None = None


class TurnState(BaseModel):
    reply: str = ""
    cards: list[PlaceCard] = Field(default_factory=list)
    assumptions: str | None = None


def _event_text(event: Any) -> str:
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    return "".join(
        part.text
        for part in parts
        if getattr(part, "text", None) and not getattr(part, "thought", False)
    )


def _places_payload(event: Any) -> dict[str, Any] | None:
    output = getattr(event, "output", None)
    if isinstance(output, dict) and isinstance(output.get("places"), list):
        return output

    actions = getattr(event, "actions", None)
    state_delta = getattr(actions, "state_delta", None) or {}
    saved = state_delta.get("destination_recommendations")
    if isinstance(saved, dict) and isinstance(saved.get("places"), list):
        return saved

    getter = getattr(event, "get_function_responses", None)
    if getter is None:
        return None
    for response in getter():
        payload = getattr(response, "response", None)
        if isinstance(payload, dict) and isinstance(payload.get("places"), list):
            return payload
    return None


def observe(state: TurnState, event: Any) -> list[dict[str, Any]]:
    """Update turn state from one ADK event and return UI messages."""
    updates: list[dict[str, Any]] = []
    payload = _places_payload(event)
    if payload is not None:
        state.cards = cards_from_payload(payload)
        assumptions = payload.get("assumptions")
        state.assumptions = assumptions if isinstance(assumptions, str) else None
        updates.append(
            {
                "type": "cards",
                "cards": [card.model_dump() for card in state.cards],
                "assumptions": state.assumptions,
            }
        )

    getter = getattr(event, "get_function_calls", None)
    if getter is not None:
        for call in getter():
            status = STATUS_BY_TOOL.get(getattr(call, "name", ""))
            if status:
                updates.append({"type": "status", "text": status})

    author = getattr(event, "author", "")
    text = _event_text(event)
    if author != ROOT_AGENT or not text:
        return updates
    if getattr(event, "partial", False):
        updates.append({"type": "reply_delta", "text": text})
        return updates
    if event.is_final_response():
        state.reply = text
    return updates


async def _require_session(user_id: str, session_id: str):
    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


async def _run_turn(
    message: str, user_id: str, session_id: str
) -> AsyncIterator[tuple[TurnState, list[dict[str, Any]]]]:
    cleaned = message.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="message is required")
    await _require_session(user_id, session_id)
    content = types.Content(role="user", parts=[types.Part(text=cleaned)])
    state = TurnState()
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            yield state, observe(state, event)
    except HTTPException:
        raise
    except Exception:
        logger.exception("agent turn failed")
        raise HTTPException(
            status_code=502,
            detail="The travel planner could not complete this turn.",
        ) from None


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sessions", response_model=SessionCreated)
async def create_session(body: SessionCreate) -> SessionCreated:
    user_id = body.user_id.strip() or DEFAULT_USER
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    return SessionCreated(session_id=session.id, user_id=user_id)


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = DEFAULT_USER) -> dict[str, Any]:
    await _require_session(user_id, session_id)
    await session_service.delete_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    return {"session_id": session_id, "deleted": True}


@app.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def post_message(session_id: str, body: ChatRequest) -> ChatResponse:
    user_id = body.user_id.strip() or DEFAULT_USER
    state = TurnState()
    async for state, _updates in _run_turn(body.message, user_id, session_id):
        pass
    return ChatResponse(
        session_id=session_id,
        user_id=user_id,
        reply=state.reply,
        cards=state.cards,
        assumptions=state.assumptions,
    )


@app.post("/sessions/{session_id}/messages/stream")
async def stream_message(session_id: str, body: ChatRequest) -> StreamingResponse:
    user_id = body.user_id.strip() or DEFAULT_USER
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    await _require_session(user_id, session_id)

    async def events() -> AsyncIterator[str]:
        state = TurnState()
        try:
            async for state, updates in _run_turn(body.message, user_id, session_id):
                for update in updates:
                    yield _sse(update)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
            yield _sse({"type": "error", "text": detail})
            return
        yield _sse(
            {
                "type": "done",
                "session_id": session_id,
                "user_id": user_id,
                "reply": state.reply,
                "cards": [card.model_dump() for card in state.cards],
                "assumptions": state.assumptions,
            }
        )

    return StreamingResponse(events(), media_type="text/event-stream")


_QUERY_METHODS = {"query", "async_query", "stream_query", "async_stream_query"}
_CREATE_SESSION_METHODS = {"create_session", "async_create_session"}
_GET_SESSION_METHODS = {"get_session", "async_get_session"}
_LIST_SESSION_METHODS = {"list_sessions", "async_list_sessions"}
_DELETE_SESSION_METHODS = {"delete_session", "async_delete_session"}


def _runtime_method(body: dict[str, Any]) -> str:
    method = body.get("class_method") or body.get("classMethod") or "stream_query"
    return str(method).strip()


def _runtime_input(body: dict[str, Any]) -> dict[str, Any]:
    payload = body.get("input")
    return payload if isinstance(payload, dict) else {}


def _message_text(message: Any) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        parts = message.get("parts") or []
        texts = [
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        if texts:
            return "".join(texts)
        text = message.get("text")
        if isinstance(text, str):
            return text
    return ""


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


async def _open_runtime_session(user_id: str, session_id: Any):
    if session_id:
        existing = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=str(session_id),
        )
        if existing is not None:
            return existing
        return await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=str(session_id),
        )
    return await session_service.create_session(app_name=APP_NAME, user_id=user_id)


async def _runtime_events(payload: dict[str, Any]) -> AsyncIterator[Any]:
    text = _message_text(payload.get("message")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="message is required")
    user_id = str(payload.get("user_id") or DEFAULT_USER).strip() or DEFAULT_USER
    session = await _open_runtime_session(user_id, payload.get("session_id"))
    content = types.Content(role="user", parts=[types.Part(text=text)])
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=content,
    ):
        yield event


async def _runtime_call(method: str, payload: dict[str, Any]) -> Any:
    user_id = str(payload.get("user_id") or DEFAULT_USER).strip() or DEFAULT_USER
    if method in _CREATE_SESSION_METHODS:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=str(payload["session_id"]) if payload.get("session_id") else None,
            state=payload.get("state") if isinstance(payload.get("state"), dict) else None,
        )
        return _jsonable(session)
    if method in _GET_SESSION_METHODS:
        session_id = payload.get("session_id")
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=str(session_id),
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return _jsonable(session)
    if method in _LIST_SESSION_METHODS:
        listed = await session_service.list_sessions(app_name=APP_NAME, user_id=user_id)
        return _jsonable(listed)
    if method in _DELETE_SESSION_METHODS:
        session_id = payload.get("session_id")
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        await session_service.delete_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=str(session_id),
        )
        return {"session_id": str(session_id), "deleted": True}
    if method in _QUERY_METHODS:
        reply = ""
        async for event in _runtime_events(payload):
            author = getattr(event, "author", "")
            text = _event_text(event)
            if author == ROOT_AGENT and text and event.is_final_response():
                reply = text
        return reply
    raise HTTPException(status_code=400, detail=f"Unsupported class method: {method}")


async def _load_runtime_body(request: Request) -> dict[str, Any]:
    """Agent Runtime forwards the query body as a JSON string, not an object."""
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Request body is required")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Request body must be JSON") from exc
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400, detail="Request body must be a JSON object"
            ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    return parsed


@app.post("/api/reasoning_engine")
async def reasoning_engine(request: Request) -> dict[str, Any]:
    body = await _load_runtime_body(request)
    method = _runtime_method(body)
    logger.info("runtime query method=%s", method)
    reply = await _runtime_call(method, _runtime_input(body))
    return {"output": reply, "response": reply}


@app.post("/api/stream_reasoning_engine")
async def stream_reasoning_engine(request: Request) -> StreamingResponse:
    body = await _load_runtime_body(request)
    method = _runtime_method(body)
    payload = _runtime_input(body)
    logger.info("runtime stream method=%s", method)

    async def lines() -> AsyncIterator[str]:
        try:
            if method in _QUERY_METHODS:
                async for event in _runtime_events(payload):
                    yield json.dumps({"output": _jsonable(event)}) + "\n"
                return
            yield json.dumps({"output": await _runtime_call(method, payload)}) + "\n"
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
            yield json.dumps({"output": {"error": detail}}) + "\n"
        except Exception:
            logger.exception("runtime stream failed")
            yield json.dumps(
                {"output": {"error": "The travel planner could not complete this turn."}}
            ) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

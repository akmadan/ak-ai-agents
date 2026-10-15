import logging
import os
import re
from functools import lru_cache
from typing import Literal

from google import genai
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types
from pydantic import BaseModel, Field

from .prompts import INPUT_GUARD_INSTRUCTION, OUTPUT_GUARD_INSTRUCTION

logger = logging.getLogger(__name__)

GUARD_MODEL = os.getenv("GUARD_MODEL", "gemini-flash-latest")

_INJECTION = re.compile(
    r"("
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules)"
    r"|disregard (your )?(system|safety) (prompt|rules)"
    r"|(reveal|print|show) (your )?(system|hidden) prompt"
    r"|you are now (a |an )?(dan|unfiltered)"
    r"|\bjailbreak\b"
    r")",
    re.IGNORECASE,
)
_CRISIS = re.compile(
    r"("
    r"\bkill myself\b"
    r"|\bsuicid(e|al)\b"
    r"|\bend my life\b"
    r"|\btake my (own )?life\b"
    r"|\bwant to die\b"
    r"|\bhow (do|can|to) i (overdose|hurt myself|cut myself)\b"
    r")",
    re.IGNORECASE,
)
_BLOCKED_REQUEST = re.compile(
    r"("
    r"\bhow to (make|synthesize|cook|build) (meth|fentanyl|a bomb|explosives)\b"
    r"|\bwrite me a prescription\b"
    r")",
    re.IGNORECASE,
)

BLOCK_TEXT = (
    "I can only help with health questions and symptoms. "
    "I can't answer questions outside that."
)
CRISIS_TEXT = (
    "I'm really sorry you're going through this. You don't have to face it alone. "
    "If you might act on thoughts of suicide or self-harm, please contact your local "
    "emergency number or a crisis line right now (in the US, call or text 988; in India, "
    "call Tele-MANAS at 14416). I can't help with methods or instructions."
)
UNSAFE_OUTPUT_TEXT = (
    "I can't diagnose you or tell you which medication or dose to take. "
    "I can share general health information for you to review with a clinician."
)
GUARD_ERROR_TEXT = (
    "I couldn't safety-check that message right now. Please try again in a moment."
)


class InputDecision(BaseModel):
    decision: Literal["allow", "block", "crisis"]
    reason: str = Field(description="Short reason with no methods or instructions.")


class OutputDecision(BaseModel):
    safe: bool
    kind: Literal["ok", "off_topic", "unsafe"]
    reason: str = Field(description="Short reason with no methods or instructions.")


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    return genai.Client()


def _text(content: types.Content | None) -> str:
    if not content or not content.parts:
        return ""
    return "\n".join(p.text for p in content.parts if p.text and not p.thought).strip()


def _reply(text: str) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=text)])
    )


def screen_input(text: str) -> str | None:
    if not text:
        return "block"
    if _CRISIS.search(text):
        return "crisis"
    if _INJECTION.search(text) or _BLOCKED_REQUEST.search(text):
        return "block"
    return None


async def _classify(instruction: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
    response = await _client().aio.models.generate_content(
        model=GUARD_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=instruction,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,
        ),
    )
    return schema.model_validate_json(response.text)


async def input_guard(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> LlmResponse | None:
    user_text = _text(callback_context.user_content)

    decision = screen_input(user_text)
    if decision is None:
        try:
            result = await _classify(
                INPUT_GUARD_INSTRUCTION, f"User message:\n{user_text}", InputDecision
            )
        except Exception:
            logger.exception("input guard failed")
            return _reply(GUARD_ERROR_TEXT)
        decision = result.decision
        logger.info("input guard: %s (%s)", decision, result.reason)

    callback_context.state["temp:input_decision"] = decision
    if decision == "crisis":
        return _reply(CRISIS_TEXT)
    if decision == "block":
        return _reply(BLOCK_TEXT)
    return None


async def output_guard(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    if llm_response.partial or callback_context.state.get("temp:input_decision") != "allow":
        return None

    draft = _text(llm_response.content)
    if not draft:
        return None

    user_text = _text(callback_context.user_content)
    try:
        result = await _classify(
            OUTPUT_GUARD_INSTRUCTION,
            f"User message:\n{user_text}\n\nDraft reply:\n{draft}",
            OutputDecision,
        )
    except Exception:
        logger.exception("output guard failed")
        return _reply(GUARD_ERROR_TEXT)

    logger.info("output guard: %s (%s)", result.kind, result.reason)
    if result.safe:
        return None
    return _reply(BLOCK_TEXT if result.kind == "off_topic" else UNSAFE_OUTPUT_TEXT)

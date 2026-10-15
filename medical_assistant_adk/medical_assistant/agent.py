import os

from google.adk.agents import Agent
from google.genai import types

from .guardrails import input_guard, output_guard
from .prompts import AGENT_INSTRUCTION

_SAFETY_SETTINGS = [
    types.SafetySetting(
        category=category,
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    )
    for category in (
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
    )
]

root_agent = Agent(
    name="medical_assistant",
    model=os.getenv("AGENT_MODEL", "gemini-flash-latest"),
    description="Answers general health questions with input and output guardrails.",
    instruction=AGENT_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.3,
        safety_settings=_SAFETY_SETTINGS,
    ),
    before_model_callback=input_guard,
    after_model_callback=output_guard,
)

from langchain_core.messages import AIMessage
from langchain_litellm import ChatLiteLLM

from config import GROQ_API_KEY, LLM


def _field(obj, key):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


class ChatModel(ChatLiteLLM):
    """Keeps the provider response fields instead of LiteLLM's client labels."""

    def _create_chat_result(self, response, **params):
        result = super()._create_chat_result(response, **params)
        usage = _field(response, "usage") or {}
        served_model = _field(response, "model")
        for generation in result.generations:
            message = generation.message
            if not isinstance(message, AIMessage):
                continue
            metadata = dict(message.response_metadata or {})
            if served_model:
                metadata["model"] = served_model
            metadata["prompt_tokens"] = int(_field(usage, "prompt_tokens") or 0)
            metadata["completion_tokens"] = int(_field(usage, "completion_tokens") or 0)
            metadata["total_tokens"] = int(_field(usage, "total_tokens") or 0)
            message.response_metadata = metadata
        return result


def get_llm() -> ChatModel:
    if not GROQ_API_KEY:
        raise RuntimeError("Set GROQ_API_KEY in medical_assistant_langgraph/.env.")
    model = LLM if LLM.startswith("groq/") else f"groq/{LLM}"
    return ChatModel(model=model, temperature=0.2)

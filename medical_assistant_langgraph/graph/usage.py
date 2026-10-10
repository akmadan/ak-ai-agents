import time

from config import LLM


def _number(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def call_record(response, step: str, latency_ms: int) -> dict:
    usage = getattr(response, "usage_metadata", None) or {}
    meta = getattr(response, "response_metadata", None) or {}
    prompt_tokens = meta.get("prompt_tokens")
    if prompt_tokens is None:
        prompt_tokens = usage.get("input_tokens")
    completion_tokens = meta.get("completion_tokens")
    if completion_tokens is None:
        completion_tokens = usage.get("output_tokens")
    total_tokens = meta.get("total_tokens")
    if total_tokens is None:
        total_tokens = usage.get("total_tokens")
    prompt_tokens = _number(prompt_tokens)
    completion_tokens = _number(completion_tokens)
    total_tokens = _number(total_tokens) or prompt_tokens + completion_tokens
    return {
        "step": step,
        "model": meta.get("model") or meta.get("model_name") or LLM,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
        "response_cost": meta.get("response_cost"),
    }


def timed_invoke(runnable, messages, step: str) -> tuple[object, dict]:
    started = time.perf_counter()
    result = runnable.invoke(messages)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return result, call_record(result, step, latency_ms)


def append_call(state: dict, record: dict) -> list[dict]:
    return [*(state.get("calls") or []), record]


def summarize_calls(calls: list[dict]) -> dict:
    models = []
    for call in calls:
        if call.get("model") and call["model"] not in models:
            models.append(call["model"])
    costs = [
        call["response_cost"]
        for call in calls
        if isinstance(call.get("response_cost"), (int, float))
    ]
    return {
        "model": models[0] if len(models) == 1 else None,
        "models": models,
        "prompt_tokens": sum(_number(call.get("prompt_tokens")) for call in calls),
        "completion_tokens": sum(_number(call.get("completion_tokens")) for call in calls),
        "total_tokens": sum(_number(call.get("total_tokens")) for call in calls),
        "latency_ms": sum(_number(call.get("latency_ms")) for call in calls),
        "response_cost": round(sum(costs), 6) if costs else None,
        "calls": calls,
    }


def with_turn_metadata(response_metadata: dict | None, calls: list[dict]) -> dict:
    metadata = dict(response_metadata or {})
    metadata["turn"] = summarize_calls(calls)
    return metadata

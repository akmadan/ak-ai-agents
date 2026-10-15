# Medical Assistant (ADK)

A text-only medical assistant built with Google ADK and Gemini. It answers general health questions, asks short follow-ups for vague symptoms, and points emergencies to urgent care. It does not diagnose or prescribe.

## Setup

Python 3.10 or newer is required.

```bash
cd medical_assistant_adk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp medical_assistant/.env.example medical_assistant/.env
```

Set `GOOGLE_API_KEY` in `medical_assistant/.env` to a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey). `AGENT_MODEL` and `GUARD_MODEL` default to `gemini-flash-latest`.

## Run

From `medical_assistant_adk/`:

```bash
adk web      # browser chat UI at http://localhost:8000
adk run medical_assistant   # terminal chat
```

If your shell exports `OTEL_EXPORTER_OTLP_ENDPOINT`, ADK tries to export traces there and fails with `No module named 'opentelemetry.exporter'`. Start it with that variable cleared:

```bash
env -u OTEL_EXPORTER_OTLP_ENDPOINT adk web
```

## HTTP server

`server.py` wraps the agent in FastAPI using the Agent Runtime container contract, the same as the LangGraph project. It listens on `0.0.0.0:$PORT` (default 8080).

```bash
python server.py
```

| Endpoint | Body |
|---|---|
| `GET /health` | none |
| `POST /api/reasoning_engine` | `{"class_method": "query", "input": {"message": "...", "session_id": "optional"}}` |
| `POST /api/reasoning_engine` | `{"class_method": "delete_session", "input": {"session_id": "..."}}` |
| `POST /api/stream_reasoning_engine` | `{"class_method": "stream_query", "input": {"message": "...", "session_id": "optional"}}` |

`query` returns `{"output": {"session_id", "user_id", "response"}}`. Pass the returned `session_id` on later turns to keep the conversation. `stream_query` returns newline-delimited JSON events and ends with an `{"output": ...}` line. An optional `user_id` scopes sessions per user.

Sessions are held in memory, so they are lost when the server restarts and are not shared across instances.

### Docker

```bash
docker build -t medical-assistant-adk .
docker run -p 8080:8080 -e GOOGLE_API_KEY=your-key medical-assistant-adk
```

The `.env` file is not copied into the image. Pass the key as an environment variable or a secret on your platform.

## Guardrails

Each turn passes through three layers:

1. **Input guard** (`before_model_callback`). Regex rules catch self-harm, prompt injection, and clearly disallowed requests without an LLM call. Anything else goes to a Gemini classifier that returns `allow`, `block`, or `crisis`. Off-topic and unsafe messages get a fixed refusal. Crisis messages get a crisis-line notice. The main model is never called for these.
2. **Gemini safety settings** on the main model block dangerous, harassing, hateful, or sexual content at medium severity and above.
3. **Output guard** (`after_model_callback`). A Gemini classifier checks the draft reply. Drafts that diagnose, name a drug or dose for the user, give harmful steps, leak instructions, or drift off topic are replaced with a refusal.

If a guard classifier call fails, the turn returns a "try again" message instead of an unchecked answer.

The output guard checks complete responses only. Leave streaming off in `adk web`; streamed chunks would reach the user before the check runs.

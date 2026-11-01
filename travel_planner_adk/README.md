# Travel Planner (ADK)

Google ADK travel planner. A supervisor delegates to three specialists: destination research, itinerary planning, and budget and feasibility. Those specialists search the web with Tavily. Destination recommendations come back as JSON `place_id` values from `travel_planner/places.py`, so a backend can map each id to an object-storage image. Flight, hotel, map, and visa tools are not connected yet.

## Setup

Python 3.11 or newer is required. [uv](https://docs.astral.sh/uv/) creates the virtual environment and installs from `pyproject.toml`.

```bash
cd travel_planner_adk
uv sync
cp travel_planner/.env.example travel_planner/.env
```

Set `GOOGLE_API_KEY` in `travel_planner/.env` to a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey). Set `TAVILY_API_KEY` to a key from [Tavily](https://tavily.com/).

## Run

From `travel_planner_adk/`:

```bash
uv run adk web
uv run adk run travel_planner
uv run uvicorn server:app --reload --port 8000
```

`adk web` is the agent dev UI. `server:app` is the API for your own UI.

## UI API

Create a session, then send messages. The reply is the planner's prose. `cards` are catalog destinations from that turn, with `image_url` set when `PLACE_IMAGE_BASE_URL` is set. Each object is `{place_id}.jpg` under that prefix. `CORS_ORIGINS` defaults to `*`.

```bash
curl -s -X POST localhost:8000/sessions -H 'content-type: application/json' -d '{"user_id":"default"}'
curl -s -X POST localhost:8000/sessions/SESSION_ID/messages \
  -H 'content-type: application/json' \
  -d '{"message":"a quiet beach week"}'
```

`POST /sessions/{session_id}/messages/stream` sends server-sent events: `status`, `reply_delta`, `cards`, and a final `done` event. Replace the in-progress bubble with `done.reply`. OpenAPI is at [http://localhost:8000/docs](http://localhost:8000/docs).

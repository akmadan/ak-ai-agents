FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    GOOGLE_GENAI_USE_VERTEXAI=FALSE \
    PORT=8000

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY server.py ./
COPY travel_planner ./travel_planner

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Keys are not baked in. Set GOOGLE_API_KEY and TAVILY_API_KEY at run time.
# Optional: AGENT_MODEL, PLACE_IMAGE_BASE_URL, CORS_ORIGINS.
CMD ["python", "server.py"]

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GOOGLE_GENAI_USE_VERTEXAI=FALSE \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install uv && uv pip install --system -r requirements.txt

COPY travel_planner ./travel_planner
COPY kagent_app.py .

EXPOSE 8080
CMD ["uvicorn", "kagent_app:app", "--host", "0.0.0.0", "--port", "8080"]

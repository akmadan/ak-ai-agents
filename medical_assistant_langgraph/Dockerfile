FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    CHROMA_DIR=/tmp/chroma_data \
    ANONYMIZED_TELEMETRY=False \
    PORT=8080

WORKDIR /app

# CPU-only torch keeps the image ~2 GB smaller than the default CUDA wheel.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the embedding model in so cold starts do not download it.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8080
CMD ["python", "server.py"]

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
LLM = os.getenv("LLM", "groq/llama-3.3-70b-versatile")

CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(ROOT / "chroma_data")))
if not CHROMA_DIR.is_absolute():
    CHROMA_DIR = (ROOT / CHROMA_DIR).resolve()

UPLOADS_DIR = ROOT / "uploads"
COLLECTION_NAME = "medical_reports"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
REPORT_TOP_K = 4
WEB_TOP_K = 5
MAX_SYMPTOM_QUESTIONS = 2

DISCLAIMER = (
    "This is not a medical diagnosis or prescription. "
    "Please confirm with a qualified clinician."
)
URGENT_CARE = (
    "If you have chest pain, trouble breathing, signs of a stroke, "
    "or severe bleeding, seek emergency care now."
)


def missing_keys() -> list[str]:
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")
    return missing

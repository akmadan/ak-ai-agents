from pathlib import Path
from uuid import uuid4

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from config import CHUNK_OVERLAP, CHUNK_SIZE
from rag.store import replace_session_chunks


def load_pages(path: Path) -> list[tuple[int, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((index, text))
        return pages
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            return [(1, text)]
        return []
    raise ValueError("Upload a PDF or text file.")


def ingest_report(path: str, session_id: str) -> dict:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Report not found: {path}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = []
    for page_num, text in load_pages(file_path):
        for piece in splitter.split_text(text):
            cleaned = piece.strip()
            if not cleaned:
                continue
            chunks.append(
                {
                    "id": str(uuid4()),
                    "text": cleaned,
                    "metadata": {
                        "session_id": session_id,
                        "source": file_path.name,
                        "page": page_num,
                    },
                }
            )

    count = replace_session_chunks(session_id, chunks)
    return {"source": file_path.name, "chunks": count}

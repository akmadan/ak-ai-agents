import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL, REPORT_TOP_K

_client: chromadb.PersistentClient | None = None
_collection = None


def get_collection():
    global _client, _collection
    if _collection is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        embedding = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding,
        )
    return _collection


def _ids_for_session(session_id: str) -> list[str]:
    try:
        existing = get_collection().get(where={"session_id": session_id})
    except Exception:
        return []
    return list(existing.get("ids") or [])


def delete_session(session_id: str) -> None:
    ids = _ids_for_session(session_id)
    if ids:
        get_collection().delete(ids=ids)


def replace_session_chunks(session_id: str, chunks: list[dict]) -> int:
    delete_session(session_id)
    if not chunks:
        return 0
    get_collection().add(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )
    return len(chunks)


def search_session(session_id: str, query: str, k: int = REPORT_TOP_K) -> list[dict]:
    if not _ids_for_session(session_id):
        return []
    result = get_collection().query(
        query_texts=[query],
        n_results=k,
        where={"session_id": session_id},
    )
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    hits = []
    for text, metadata in zip(documents, metadatas):
        hits.append({"text": text, "metadata": metadata or {}})
    return hits

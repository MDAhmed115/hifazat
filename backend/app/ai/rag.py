# backend/app/ai/rag.py
"""RAG + OCR helpers (ChromaDB + sentence-transformers + pytesseract).

Runs fully local, no cloud. If the heavy deps are not installed the
functions degrade to a no-op so the rest of the prototype still runs —
installing them is optional (see README commands).
"""
from ..config import settings

_COLLECTION = "scam_knowledge"


def _get_collection():
    try:
        import chromadb
    except ImportError:
        return None
    client = chromadb.Client()  # in-memory / local persistent on disk is fine too
    return client.get_or_create_collection(_COLLECTION)


def index_documents(docs: list[str]) -> int:
    """Add reference scam descriptions to the local vector store."""
    coll = _get_collection()
    if coll is None:
        return 0
    for i, doc in enumerate(docs):
        coll.upsert(ids=[f"doc-{i}"], documents=[doc])
    return len(docs)


def retrieve_similar(query: str, k: int = 3) -> list[dict]:
    """Return up to k similar reference texts (sources for the decision)."""
    coll = _get_collection()
    if coll is None:
        return []
    try:
        res = coll.query(query_texts=[query], n_results=min(k, max(coll.count(), 1)))
        docs = res.get("documents", [[]])[0]
        dists = res.get("distances", [[]])[0]
        return [
            {"text": d, "distance": dists[j] if j < len(dists) else None}
            for j, d in enumerate(docs)
        ]
    except Exception:
        return []


def ocr_image(path: str) -> str:
    """Extract text from an uploaded scam screenshot/document (pytesseract)."""
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(path))
    except Exception:
        return ""

# backend/app/ai/rag.py
"""RAG over the mock official documents. Local only: ChromaDB + MiniLM."""
import glob
import os
import re

from .classifier import _call_groq, _extract_json

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCS_DIR = os.path.join(BASE_DIR, "docs_corpus")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
COLLECTION = "hifazat_docs"
EMBED_MODEL = "all-MiniLM-L6-v2"
TOP_K = 3
# cosine distance: 0 = identical meaning. Chunks farther than this are ignored.
MAX_DISTANCE = float(os.environ.get("RAG_MAX_DISTANCE", "0.75"))

REFUSAL_EN = "I don't have this in official documents."
REFUSAL_UR = "یہ معلومات سرکاری دستاویزات میں موجود نہیں ہیں۔"

SYSTEM = (
    "You answer questions for Pakistani citizens about relief schemes. Use ONLY the CONTEXT given. "
    "Never use outside knowledge. Each context block starts with its document file name in [brackets]. "
    "If the context does not clearly answer the question, set answerable to false. "
    "If answerable, write a short answer in simple English and in simple Urdu, and put the file name "
    "in square brackets after each claim in the English answer, like [01_file.md]. "
    "Output ONLY JSON: "
    '{"answerable": true, "answer_en": "...", "answer_ur": "...", "used_docs": ["file.md"]}'
)

_model_cache = None


def _model():
    global _model_cache
    if _model_cache is None:
        from sentence_transformers import SentenceTransformer
        _model_cache = SentenceTransformer(EMBED_MODEL)
    return _model_cache


def _client():
    import chromadb
    from chromadb.config import Settings
    return chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))


def _load_chunks():
    """One chunk per paragraph. The doc title is added to the text that gets embedded."""
    chunks = []
    for path in sorted(glob.glob(os.path.join(DOCS_DIR, "*.md"))):
        name = os.path.basename(path)
        with open(path, "r", encoding="utf-8-sig") as f:
            text = f.read()
        title = name
        for line in text.splitlines():
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                break
        n = 0
        for para in re.split(r"\n\s*\n", text):
            para = para.strip()
            if len(para) < 30 or para.startswith("#"):
                continue
            n += 1
            chunks.append({"id": "%s-%d" % (name, n), "doc": name, "title": title,
                           "text": para, "embed_text": title + ". " + para})
    return chunks


def build_index():
    """(Re)build the vector index from docs_corpus. Returns number of chunks."""
    chunks = _load_chunks()
    if not chunks:
        raise RuntimeError("No .md files found in " + DOCS_DIR)
    client = _client()
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    emb = _model().encode([c["embed_text"] for c in chunks]).tolist()
    col.add(ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[{"doc": c["doc"], "title": c["title"]} for c in chunks],
            embeddings=emb)
    return len(chunks)


def _get_collection():
    client = _client()
    try:
        col = client.get_collection(COLLECTION)
        if col.count() > 0:
            return col
    except Exception:
        pass
    build_index()
    return _client().get_collection(COLLECTION)


def _refusal(error=None):
    out = {"answered": False, "answer_en": REFUSAL_EN, "answer_ur": REFUSAL_UR, "sources": []}
    if error:
        out["error"] = error
    return out


def rag_query(question):
    """Returns {answered, answer_en, answer_ur, sources:[{doc, excerpt}]}. NEVER raises."""
    try:
        q = (question or "").strip()
        if not q:
            return _refusal()

        col = _get_collection()
        emb = _model().encode([q]).tolist()
        res = col.query(query_embeddings=emb, n_results=TOP_K)

        hits = []
        for doc_text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            if dist <= MAX_DISTANCE:
                hits.append({"doc": meta["doc"], "text": doc_text, "distance": round(float(dist), 3)})
        if not hits:
            return _refusal()  # nothing close enough: refuse WITHOUT calling the AI

        context = "\n\n".join("[%s] %s" % (h["doc"], h["text"]) for h in hits)
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "CONTEXT:\n" + context + "\n\nQUESTION: " + q},
        ]
        data = _extract_json(_call_groq(messages))
        if not data.get("answerable"):
            return _refusal()

        answer_en = str(data.get("answer_en", "")).strip()
        answer_ur = str(data.get("answer_ur", "")).strip()
        if not answer_en:
            return _refusal()

        used = set(str(x) for x in (data.get("used_docs") or []))
        chosen = [h for h in hits if h["doc"] in used] or hits[:1]
        sources, seen = [], set()
        for h in chosen:
            key = (h["doc"], h["text"])
            if key not in seen:
                seen.add(key)
                sources.append({"doc": h["doc"], "excerpt": h["text"][:300]})
        return {"answered": True, "answer_en": answer_en,
                "answer_ur": answer_ur or REFUSAL_UR, "sources": sources}
    except Exception as e:
        return _refusal(type(e).__name__ + ": " + str(e)[:150])

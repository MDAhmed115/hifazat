# scripts/load_rules_docs.py
"""(Re)build the RAG index:  python scripts/load_rules_docs.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.ai.rag import build_index, DOCS_DIR, CHROMA_DIR

print("Reading documents from:", DOCS_DIR)
n = build_index()
print("Indexed %d chunks into %s" % (n, CHROMA_DIR))

"""Agents-chamber RAG pipeline.

Splits cleanly from ``agents/execution/handlers/rag_search.py`` (which
is the *query* side) — this package is the *indexing* side: chunkers,
embedder dispatch, and the Dramatiq actor that fills a VectorCollection
from a source File.

Submodules:
    chunkers:  pure functions that split text into ordered chunks.
    embedder:  provider dispatch shared with the rag_search handler.
    workers:   the ``agents.rag.index_document`` Dramatiq actor.
"""

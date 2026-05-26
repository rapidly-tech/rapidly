"""VectorCollection CRUD + indexing trigger surface.

The collection is the parent of VectorChunk rows. Workflows author
a collection (name + embedding model + dim), upload source files,
and trigger indexing — the rag_search node then queries against
the collection by id.

Per-file conventions:
    api.py:       HTTP handlers (``/v1/agents/vector-collections/*``)
    actions.py:   business logic
    queries.py:   ``VectorCollectionRepository``
    types.py:     request/response Pydantic schemas
    permissions.py: ``VectorCollectionsRead`` / ``VectorCollectionsWrite``
"""

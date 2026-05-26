"""LLM usage read API.

Read-only surface for the M4.7d usage tracking. Writes happen
inside the LLM handler — this submodule only exposes the data
to dashboards + budget-alert tooling.

Per-file conventions:
    api.py:         HTTP handlers
    actions.py:     read + rollup business logic
    queries.py:     Repository + grouped-aggregate helpers
    types.py:       response Pydantic schemas (read-only)
    permissions.py: auth dependencies
"""

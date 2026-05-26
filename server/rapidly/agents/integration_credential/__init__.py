"""IntegrationCredential — per-workspace API keys for outbound integrations.

Storage of LLM / embedding provider credentials. Consumer wiring
(embedder + LLM handler resolving credentials at runtime) lands
in M4.7b.

Per-file conventions:
    api.py:         HTTP handlers
    actions.py:     business logic
    queries.py:     repository + encrypt/decrypt helpers
    types.py:       request/response Pydantic schemas
    permissions.py: auth dependencies
"""

"""Dataset + DatasetCase CRUD.

Foundation for the eval runner (M4.8b). This submodule ships
the data model + HTTP surface; the runner that drives a workflow
against every case in a dataset lands in M4.8b.

Per-file conventions:
    api.py:         HTTP handlers (dataset + case routes)
    actions.py:     business logic
    queries.py:     Repository + workspace-scoped readable statement
    types.py:       request/response Pydantic schemas
    permissions.py: auth dependencies
"""

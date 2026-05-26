"""Eval runner — drives a workflow against every case in a dataset.

The actor in ``workers.py`` is the heavy lifter; ``api.py``
exposes the trigger + read surface. The runner reuses the
existing Run + engine machinery (one synthetic Run per case)
so debugging a failing case lands the operator in the same
NodeRun timeline they use for production runs.

Per-file conventions match the other agents submodules:
    api.py:         HTTP handlers
    actions.py:     business logic (CRUD + trigger)
    queries.py:     Repository + readable statements
    types.py:       Pydantic schemas
    permissions.py: auth dependencies
    workers.py:     Dramatiq actor + comparator
"""

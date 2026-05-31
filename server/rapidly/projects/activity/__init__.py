"""Activity module: append-only audit log for work items.

Read endpoints live in ``api.py``.  Writes flow through ``emit`` —
work-item, comment, and relation actions call it after their state-
mutating step.
"""

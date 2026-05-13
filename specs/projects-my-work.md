# Projects — "My Work" cross-project work-item view

## Goal

Give a signed-in user a single page that lists every non-archived work item assigned to them across every project in every workspace they belong to. Lives at `/preview/my-work`.

## Why now

- The work-item list endpoint already supports filtering by project and state, but not by assignee. A "what am I working on" view is the most-used screen in any PM app and the easiest way to validate that the work-item domain actually delivers value.
- Adds one filter parameter to one existing endpoint — no new tables, no new routes. Strictly additive.

## Backend change

`server/rapidly/projects/work_item/actions.py::list_items` and `server/rapidly/projects/work_item/api.py::list_items` gain one parameter:

```
assigned_to_me: bool = False
```

When `True`:

- If the caller is a **user principal**, narrow the SQL `SELECT` with a sub-query:
  ```sql
  WHERE work_items.id IN (
      SELECT work_item_id FROM work_item_assignees
      WHERE user_id = :auth_user_id
        AND deleted_at IS NULL
  )
  ```
- If the caller is a **workspace token**, reject with `BadRequest` — `assigned_to_me` has no meaning for a workspace-bound principal because there is no single user to bind to.

When `False` (default), behaviour is unchanged.

## Why a server-side flag, not a `assignee_id=<self>` filter

`assigned_to_me=true` lets the action read the user id directly off `auth_principal.subject.id` and reject workspace tokens at the action layer. The alternative — a generic `assignee_id` filter the caller fills in — would either (a) let workspace tokens forge "show user X's items" queries, or (b) need an extra check to assert `assignee_id == auth_principal.subject.id`. Same outcome, more surface, more invariants to defend. Reject the temptation.

## Tests

In `server/tests/projects/work_item/test_actions.py`:

1. `test_list_assigned_to_me_narrows_to_user_assignments` — user A has one assigned item and one unassigned item; with `assigned_to_me=True`, only the assigned row comes back.
2. `test_list_assigned_to_me_rejects_workspace_token` — workspace principal + `assigned_to_me=True` → `BadRequest`.
3. `test_list_assigned_to_me_false_returns_all_readable` — happy path with the flag off matches the pre-existing behaviour (no regression).

## Frontend

- New page `clients/apps/web/src/app/(main)/preview/my-work/page.tsx`:
  - Header "My work" + "Across all projects you're a member of."
  - List of work items rendered as compact rows: identifier prefix + sequence number + title + project identifier badge + state pill.
  - Empty state when zero results: "Nothing assigned to you. Star a project to follow it from the Projects rail."
  - Loading skeleton.
- Link from `/preview` index card grid — replaces the implicit single-card layout with "All projects" + "My work".

Frontend uses the existing `useWorkItems(...)` hook with `assigned_to_me: true`.

## Rollout & risk

- **Rollout**: same `/preview` implicit-flag approach.
- **Failure mode**: a logic flip on the sub-query could surface other users' assignments. **Mitigation**: `test_list_assigned_to_me_narrows_to_user_assignments` pins the user filter.
- **Kill criterion**: drop the param + the frontend page. The page can be removed in one revert; the param can be removed once no caller passes `assigned_to_me=true`.

## Definition of Done

- 3 new pytest cases pass.
- mypy + `ruff check` + `ruff format --check` clean (per [[feedback-ruff-format-gate]]).
- Frontend tsc + eslint clean.
- PR description stamps the standard `feedback_pr_quality_checklist` template.

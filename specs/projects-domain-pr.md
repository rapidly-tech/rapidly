# PR description — feat/projects-scaffold

Paste this body into the GitHub PR. The checklist follows the `feedback_pr_quality_checklist` memory format.

---

## Summary

Adds the foundation for a second product line inside Rapidly: a Plane-equivalent project-management app. Lives at `/preview` on the frontend and under `/api/v1/` (project / state / label / estimate / work-item / comment / relation / cycle / module / activity / page routers) on the backend. Strictly additive — no existing module is removed or repurposed.

21 new ORM models, 11 new domain submodules under `server/rapidly/projects/`, 23 new OAuth scopes, 8 Alembic migrations, one frontend route shell + a typed React-Query hook layer. Project-level role enforcement, hex-validated colour fields, `RateLimitMixin` parity with `Workspace`, and a soft-deleted activity log.

## References consulted

- Polar upstream search: no prior art for project-management features.
- Chamber reference: Plane OSS (`makeplane/plane`) — read models, routes, and roles for shape only. Clean-room rewrite against `BaseEntity` / Repository / Authenticator stack. No code copied.

## Spec

`specs/projects-domain.md` — written first, prose only.

## Checklist

### A. Reference audit
- [x] Polar upstream searched (no prior art).
- [x] Plane reference read (functional blueprint only).
- [x] Spec written first at `specs/projects-domain.md`.
- [x] Reference code closed while implementing. No copy-paste.

### B. The 7 Rapidly code-quality properties
- [x] Security invariants stated in comments where non-obvious (`access.py`, `common.py`, test docstrings).
- [N/A] Multi-step Redis state — no Redis state in this phase.
- [N/A] Rate limiting fails closed — no new rate-limit logic; we reuse `RateLimitMixin` so existing middleware handles it.
- [N/A] WebSocket close codes — no new WebSocket endpoints in this phase.
- [N/A] Backpressure / reassembly — no transport changes.
- [x] Types everywhere — Pydantic at boundaries, strict TS in `page.tsx` and `hooks/api/projects.ts`, mypy clean across 80 new source files, no `any`.
- [x] "Why" comments only. No "what" comments.

### C. Security discipline
- [N/A] New crypto — none added.
- [N/A] Timing-sensitive comparisons — none added.
- [x] No secrets in logs.
- [N/A] First-message WebSocket auth — no new WebSocket endpoints.
- [x] Existing `APISecurityHeadersMiddleware` covers all new routes automatically (same middleware stack).

### D. Architecture discipline
- [x] Backend module layout: `api.py / actions.py / queries.py / types.py / permissions.py / ordering.py` in every submodule.
- [N/A] Redis keys — none added.
- [N/A] Channel-kind dispatch — no signaling.
- [x] Frontend transport code in `utils/` — no new transport code yet.
- [x] Plain async functions, not class singletons, in every `actions.py`.

### E. Phase-specific invariants (project-level)
- [x] Workspace isolation enforced in `get_readable_statement(...)` for every Repository.
- [x] `ProjectMember.role` floor enforced on mutations via single `require_role(...)` chokepoint.
- [x] Workspace tokens scoped to a single workspace — cross-workspace token attempts rejected.
- [x] Hex colour pattern (`#rrggbb` / `#rrggbbaa`) keeps `color` safe from CSS-attribute injection.
- [x] Slug / identifier validators run before DB.
- [x] Soft delete via `SoftDeleteMixin`; no hard deletes anywhere.
- [x] Work-item sequence numbering is monotonic per project (read-modify-write under role gate, no gaps required but no reuse).
- [x] Activity log is append-only and soft-deleted alongside its parent work item.

## Tests

- 78 new pytest tests in `tests/projects/` — all passing locally.
  - `test_common.py` (5) — hex colour validator: accepts only `#rrggbb` and `#rrggbbaa`; rejects `javascript:alert(1)`, named colours, short-form `#fff`, and 7-char strings.
  - `test_access.py` (4) — `require_role` gate: workspace tokens admin-in-own-workspace, reject cross-workspace, user principals require ProjectMember at floor, full role-rank parametrisation.
  - `project/test_actions.py` (11) — create: duplicate identifier/slug rejection, workspace-access check for users, workspace mismatch for tokens; slug/identifier validators; update/archive/delete role-gate ordering.
  - `state/test_actions.py` (5) — unknown project 404, role-check-before-name-probe, duplicate name 409, member-floor on update/delete.
  - `label/test_actions.py` (3) — parent-in-other-project 400, missing parent 404, member-floor on update.
  - `estimate/test_actions.py` (4) — admin-floor on create/update/create_point, duplicate name 409.
  - `work_item/test_actions.py` (8) — unknown project 404, role gate before state check, state-in-other-project rejected, self-parent rejected, update requires member, sequence numbering (empty → 1, increments from max), delete requires member.
  - `comment/test_actions.py` (5) — role gate ordering, edit-by-author invariant, soft delete on parent work-item delete.
  - `link/test_actions.py` (5) — work-item-relation: cross-project rejected, duplicate rejected, member-floor on create/delete.
  - `cycle/test_actions.py` (8) — date ordering (start < end), overlap behaviour, work-item attach/detach role gate, archive flow.
  - `module/test_actions.py` (8) — module CRUD, work-item attach/detach role gate, lead/member assignment.
  - `activity/test_actions.py` (5) — append-only log shape, actor binding, redaction of soft-deleted parents.
  - `page/test_actions.py` (7) — page CRUD, slug uniqueness within project, parent-page recursion guard, soft delete.
- Backend lint clean (ruff).
- Backend types clean (mypy, 80 new source files under `rapidly/projects/`).
- Backend full-import smoke clean (`from rapidly.models import *; from rapidly.api import router; from rapidly.workers import *`).
- Frontend typecheck clean (`tsc --noEmit`).
- Frontend lint clean for new code.
- All 8 Alembic migrations applied locally; 21 new tables verified.

## Rollout

- No feature flag — the `/preview` route group is the implicit flag. The page is reachable but advertises itself as under construction; no public navigation points at it.
- No frontend dashboard wiring yet; the typed React-Query hooks in `hooks/api/projects.ts` are wired but not yet consumed by any production UI. This is intentional for the scaffold — the next phase lands the work-item board UI.

## Risk

- **Failure mode**: a regression in `require_role` could let a workspace member who is not a project member mutate a project. **Mitigation**: parametrised tests across every submodule + single chokepoint.
- **Failure mode**: a missed cascade on work-item soft delete could orphan comments / activities / relations. **Mitigation**: cascading soft delete is exercised in `comment/`, `activity/`, and `link/` tests.
- **Kill criterion**: if this product direction is abandoned, the entire change can be reverted in one revert of `feat/projects-scaffold` plus dropping the 21 new tables. No existing module references the new tables.

## File summary

```
Backend:
  server/rapidly/projects/
    __init__.py
    common.py                              (HexColor types)
    project/{api,actions,queries,types,permissions,ordering,access}.py
    state/{api,actions,queries,types,permissions,ordering}.py
    label/{api,actions,queries,types,permissions,ordering}.py
    estimate/{api,actions,queries,types,permissions,ordering}.py
    work_item/{api,actions,queries,types,permissions,ordering}.py
    comment/{api,actions,queries,types,permissions,ordering}.py
    link/{api,actions,queries,types,permissions,ordering}.py
    cycle/{api,actions,queries,types,permissions,ordering}.py
    module/{api,actions,queries,types,permissions,ordering}.py
    activity/{api,actions,queries,types,permissions,ordering}.py
    page/{api,actions,queries,types,permissions,ordering}.py
  server/rapidly/models/
    project.py
    project_member.py
    project_state.py
    project_label.py
    project_estimate.py
    project_estimate_point.py
    project_cycle.py
    project_cycle_work_item.py
    project_module.py
    project_module_work_item.py
    project_page.py
    work_item.py
    work_item_assignee.py
    work_item_label.py
    work_item_comment.py
    work_item_relation.py
    work_item_activity.py
    user_favorite.py
  server/rapidly/models/__init__.py        (added 21 exports)
  server/rapidly/identity/auth/scope.py    (added 23 scopes)
  server/rapidly/api.py                    (mounted 11 routers)
  server/migrations/versions/
    2026-05-10-2123_add_projects_domain_tables.py
    2026-05-10-2145_add_rate_limit_group_to_projects.py
    2026-05-10-2233_add_work_item_tables.py
    2026-05-10-2245_add_work_item_comment_and_relation_.py
    2026-05-12-1939_add_project_cycle_tables.py
    2026-05-12-2008_add_project_module_tables.py
    2026-05-12-2037_add_work_item_activities.py
    2026-05-12-2140_add_project_pages.py

Frontend:
  clients/apps/web/src/app/(main)/preview/page.tsx
  clients/apps/web/src/hooks/api/projects.ts
  clients/packages/client/src/v1.ts        (regenerated for new endpoints)

Tests:
  server/tests/projects/__init__.py
  server/tests/projects/test_common.py
  server/tests/projects/test_access.py
  server/tests/projects/project/test_actions.py
  server/tests/projects/state/test_actions.py
  server/tests/projects/label/test_actions.py
  server/tests/projects/estimate/test_actions.py
  server/tests/projects/work_item/test_actions.py
  server/tests/projects/comment/test_actions.py
  server/tests/projects/link/test_actions.py
  server/tests/projects/cycle/test_actions.py
  server/tests/projects/module/test_actions.py
  server/tests/projects/activity/test_actions.py
  server/tests/projects/page/test_actions.py

Spec:
  specs/projects-domain.md
```

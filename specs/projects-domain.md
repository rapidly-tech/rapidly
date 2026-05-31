# Projects domain — phase 1 scaffold

## Goal

Add a second product line inside Rapidly: a Plane-equivalent project-management app (workspaces → projects → work items → cycles, modules, pages, views) on the existing FastAPI + Next.js stack, alongside the current file-sharing product. Mounted under `/preview` while in progress.

## Non-goals

- No removal of, or change to, existing file-sharing, billing, customers, sharing, or storefront code. Everything is additive.
- No new brand. Same "Rapidly" branding throughout.
- No work-item, cycle, module, view, page, intake, or activity implementation in phase 1 — those come later.
- No `MobX`. State stays on TanStack Query + Zustand, matching the rest of the frontend.

## References consulted

- **Polar upstream (`polarsource/polar`)** — no prior art for project-management features.
- **Plane OSS** (`/home/admin1/Downloads/plane-preview (1)/plane-preview`) — the functional blueprint. Django + DRF backend, React Router v7 frontend, Hocuspocus realtime service.
- Re-implementation is clean-room: we read Plane's models and routes for shape (Workspace → Project → State → Label → Estimate, ProjectMember roles, hex-coloured tags, Fibonacci estimation), then wrote the equivalent against our `BaseEntity` / Repository / Authenticator stack. No code copied.

## Phase 1 scope

### Backend (`server/rapidly/projects/`)

Four submodules, each following the standard `api.py / actions.py / queries.py / types.py / permissions.py / ordering.py` layout:

| Submodule | Resource | API prefix | Notes |
|-----------|----------|------------|-------|
| `project/` | Project + ProjectMember | `/api/projects` | Full CRUD + archive/unarchive; creator auto-joins as project admin |
| `state/` | ProjectState | `/api/project-states` | StateGroup buckets (backlog/unstarted/started/completed/cancelled/triage), sequence float for ordering |
| `label/` | ProjectLabel | `/api/project-labels` | Hierarchical via parent_id; parent must belong to same project |
| `estimate/` | ProjectEstimate + ProjectEstimatePoint | `/api/project-estimates` | Includes nested points endpoint at `/points` |

Shared helper: `projects/project/access.py` — `require_role(...)` gate enforces ProjectMember role floor on mutations. Workspace tokens bypass with implicit admin in their own workspace.

Shared types: `projects/common.py` — `HexColor` and `OptionalHexColor` annotated string types with strict `#rrggbb` / `#rrggbbaa` pattern.

### ORM models (`server/rapidly/models/`)

Flat files, re-exported from `models/__init__.py`:

- `project.py` — `Project` (RateLimitMixin + BaseEntity), `ProjectVisibility` (private/public)
- `project_member.py` — `ProjectMember`, `ProjectMemberRole` (admin/member/guest)
- `project_state.py` — `ProjectState`, `StateGroup` (six-bucket enum)
- `project_label.py` — `ProjectLabel` (self-referential parent)
- `project_estimate.py` — `ProjectEstimate`, `EstimateType` (points/categories/time)
- `project_estimate_point.py` — `ProjectEstimatePoint`

### Migrations

- `2026-05-10-2123_add_projects_domain_tables.py` — creates 6 tables. Hand-edited to supply `enum_klass` to each `StringEnum(...)` column (alembic-autogen loses that argument).
- `2026-05-10-2145_add_rate_limit_group_to_projects.py` — adds the `rate_limit_group` column required by `RateLimitMixin`. `server_default = RateLimitGroup.default.value` so existing rows backfill without a separate data migration.

### OAuth scopes (`identity/auth/scope.py`)

Eight new scopes registered with display names: `projects:read/write`, `project_states:read/write`, `project_labels:read/write`, `project_estimates:read/write`. Reserved `web_read`/`web_write` honoured. Workspace `web_write` + `projects_write` is the standard combination for dashboard mutations.

### Frontend (`clients/apps/web/src/app/(main)/preview/`)

- `page.tsx` — index card grid linking to future subpages. Server component, uses the emerald palette, Tailwind v4 utility classes, no client JS.
- No new dependencies added. Existing `/` (file-sharing landing) untouched.

## Security model

| Subject | Read | Mutate state/label | Mutate estimate | Mutate project |
|---------|------|---------------------|-----------------|----------------|
| Workspace member (no project role) | ✅ project (visibility) | ❌ | ❌ | ❌ |
| ProjectMember.guest | ✅ project + nested | ❌ | ❌ | ❌ |
| ProjectMember.member | ✅ | ✅ | ❌ | ✅ update only |
| ProjectMember.admin | ✅ | ✅ | ✅ | ✅ all incl. archive/delete |
| Workspace-scoped token (own workspace) | ✅ | ✅ | ✅ | ✅ |
| Workspace-scoped token (other workspace) | ❌ | ❌ | ❌ | ❌ |

The `require_role(...)` helper is the single chokepoint. Drift would be a privilege-escalation inside a workspace; the regression is caught by `tests/projects/test_access.py` (12 parametrised assertions).

Other security disciplines applied:
- Every query goes through `get_readable_statement(auth_subject)` — workspace isolation enforced at the SQL layer.
- Hex colour pattern keeps `color` safe from CSS injection (rendered into `style` attributes downstream).
- Slug + identifier validated server-side; identifier upper-cased and alphanumeric-only; slug lower-cased and `[a-z0-9-]` only.
- `RateLimitMixin` on `Project` lets the gateway throttle per-project rate-limit tier when the work-item endpoints land.
- No new WebSocket endpoints in phase 1.

## Reuse map

| Need | Reused infra |
|------|--------------|
| User + workspace + membership | `identity/`, `platform/workspace`, `platform/user` |
| API auth + scope | `identity/auth.Authenticator` + new Scope values |
| Workspace isolation | `WorkspaceMembership` lookup pattern |
| Soft delete + audit timestamps | `BaseEntity` + `SoftDeleteMixin` |
| Rate limit tier | `RateLimitMixin` (same pattern as `Workspace`, `OAuth2Client`) |
| Pagination | `core.pagination.paginate` + `PaginatedList.from_paginated_results` |
| Sorting | `core.ordering.SortingGetter` + per-resource `SortProperty` enums |
| OpenAPI client | regenerates against the new `/api/projects/*` endpoints — no manual SDK code |

## Out of scope (next phases)

1. **Work items** — `work_item/`, `comment/`, `link/`, `activity/` submodules. The activity log will emit through the existing `analytics/event` + `eventstream` SSE infrastructure.
2. **Cycles, modules, views** — organisers built on top of work items.
3. **Collaborative pages** — `page/` submodule, Yjs sync via `y-py` extension to the existing FastAPI WebSocket signaling layer.
4. **Triage, drafts, favourites, recents.**
5. **Notifications + webhooks rebind** — register the new event types in `messaging/`. Zero new infra.
6. **Frontend dashboards** — the `(preview)` route group fills out with TanStack Query–driven pages against the generated client.

## Risk

| Risk | Mitigation |
|------|------------|
| Existing file-sharing product regresses | Strict additive policy; no shared modules edited beyond `models/__init__.py`, `api.py`, `scope.py` (additive lines only). 213 total routes verified. |
| Alembic StringEnum autogen drift on future migrations | Tracked: when autogen produces `StringEnum(length=N)` without an enum class, hand-edit to add it. Consider a custom `render_item` hook later. |
| Premature optimisation of the API surface | Phase 1 ships CRUD only. No work-item references yet, so schemas can still evolve. |
| Tests use heavy mocking | Action-level tests are pinned on the *role-gate ordering* and *uniqueness check ordering*, not deep SQLAlchemy plumbing. They will catch a regression in the auth gate without needing a real DB. |

## Kill criterion

If the projects domain is dropped before public release, removing it is a single revert of `feat/projects-scaffold` plus dropping the 6 tables. No live data references the new tables from existing modules.

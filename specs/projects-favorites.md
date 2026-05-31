# Projects — User Favorites (phase 2 follow-up)

## Goal

Let signed-in users star project-domain entities (projects, cycles, modules, pages, work items) so they appear in a "Favorites" rail on `/preview`. The `user_favorites` table and OAuth scopes were added in PR #627 but no API or UI consumes them.

## Why now

- The `/preview` index has three dead cards (`/preview/states`, `/preview/labels`, `/preview/estimates`) — those configs are per-project and already accessible from the project detail page. The right fix is to replace those cards with a Favorites rail.
- The `user_favorites` table has a UNIQUE `(user_id, entity_type, entity_id)` constraint and a `UserFavoriteEntityType` enum (`project | cycle | module | page | work_item`). Everything is in place except the API and the React surface.
- Memory ([project_projects_domain](memory:project_projects_domain)) flags `user_favorites` as "out of scope for phase 1." This is the natural phase-2 follow-up.

## Out of scope

- Reordering favorites — backend returns by `created_at desc` and the UI surfaces that order. A future PR can add an explicit `position` column if users complain.
- Cascade soft-delete when the target entity is deleted — model docstring already notes "handled by a worker out of scope for phase 1." Still out of scope here. We accept the small consistency window.
- Workspace-token authentication — favorites are user-bound by definition. Workspace tokens are rejected at the auth layer.

## Data model (already in place)

`user_favorites` columns:

| Column | Type | Notes |
|---|---|---|
| id | UUID | from `BaseEntity` |
| user_id | UUID | FK → users.id, ON DELETE CASCADE |
| entity_type | StringEnum(16) | `UserFavoriteEntityType` |
| entity_id | UUID | no FK — polymorphic |
| created_at / modified_at / deleted_at | timestamptz | from `BaseEntity` + `SoftDeleteMixin` |

UNIQUE `(user_id, entity_type, entity_id)` guarantees you can't favorite the same thing twice. The polymorphic shape is intentional: a single table beats five nullable FKs, and the action layer enforces that the entity exists and is readable.

## Backend

New submodule `server/rapidly/projects/favorite/` following the standard layout:

- `types.py` — `UserFavorite` (response), `UserFavoriteCreate` (`entity_type`, `entity_id`). No `Update` schema; favorites are immutable. The PATCH route is omitted entirely.
- `permissions.py` — `UserFavoritesRead` and `UserFavoritesWrite`, both `allowed_subjects={User}`. Workspace tokens are rejected at the dependency layer, not in actions. Required scopes: `user_favorites_read` / `user_favorites_write` plus the matching `web_*` scope.
- `queries.py` — `UserFavoriteRepository`. `get_readable_statement(...)` filters strictly to `UserFavorite.user_id == auth_principal.subject.id`. No project/workspace join needed.
- `actions.py` — `get`, `list`, `create`, `delete`. `create` does the entity-resolution check (see below). `delete` is a soft delete via the mixin.
- `api.py` — `GET /` (paginated list, optional `entity_type` filter), `GET /{id}`, `POST /` (create or 409 on conflict), `DELETE /{id}`.
- `ordering.py` — `UserFavoriteSortProperty` with `created_at` default `desc`.

### Entity-resolution check (the only non-obvious part)

Before persisting a favorite, the action layer must verify the target entity exists AND is readable by the user. Without this check, a user could favorite a UUID of a project in someone else's workspace; later `GET /` would return rows the user can't expand into anything they're allowed to see.

The check uses each domain's existing `Repository.get_readable_statement(...)`, dispatched by `entity_type`:

| entity_type | Repository | Notes |
|---|---|---|
| `project` | `ProjectRepository` | workspace-membership gate |
| `cycle` | `ProjectCycleRepository` | inherits project's gate |
| `module` | `ProjectModuleRepository` | inherits project's gate |
| `page` | `ProjectPageRepository` | inherits project's gate |
| `work_item` | `WorkItemRepository` | inherits project's gate |

If the entity isn't readable → `ResourceNotFound`. We deliberately return 404 (not 403) so we don't leak the existence of entities the user can't see.

### Duplicates

The UNIQUE constraint means a duplicate insert raises `IntegrityError`. We catch that at the action layer and convert to `ResourceAlreadyExists` (409), so the API surface is consistent. Idempotent semantics are tempting but out of scope — clients can handle 409 trivially.

## Tests (`tests/projects/favorite/test_actions.py`)

1. `test_create_persists_and_returns_row` — happy path: user can favorite a project they're a member of; subsequent `GET /` returns it.
2. `test_create_rejects_unreadable_entity` — user A cannot favorite a project in workspace B (returns 404, no row written).
3. `test_create_rejects_unknown_entity_id` — random UUID returns 404.
4. `test_create_rejects_duplicate` — second favorite of the same `(user, entity_type, entity_id)` raises `ResourceAlreadyExists`.
5. `test_create_rejects_workspace_token` — at the auth-dependency level. Route-level test, not action-level.
6. `test_list_returns_only_own` — user A only sees their own favorites, never user B's.
7. `test_list_filters_by_entity_type` — `?entity_type=project` excludes work_item favorites.
8. `test_delete_owned` — user A deletes their favorite, row is soft-deleted, subsequent `GET` returns 404.
9. `test_delete_not_owned` — user A cannot delete user B's favorite (returns 404 from `get_readable_statement`).
10. `test_dispatch_each_entity_type` — parametrised over the 5 entity types, asserting each Repository is consulted exactly once and a wrong-type lookup is not attempted.

## Frontend

### Hook surface

`hooks/api/projects.ts` gains:

```ts
useUserFavorites({ entity_type?: UserFavoriteEntityType })
useCreateUserFavorite()   // mutation
useDeleteUserFavorite()   // mutation
```

The list invalidates on create/delete. No optimistic updates — the round-trip is fast and the failure modes (conflict / not found) are easier to surface honestly.

### UI changes

- **`/preview/page.tsx`** — replace the 4 cards with: (1) a Favorites rail listing the user's favorites grouped by `entity_type` with click-through links; (2) a single "Projects →" card. The dead `/preview/states`, `/preview/labels`, `/preview/estimates` routes disappear.
- **`/preview/projects/page.tsx`** — each project row gets a star toggle. Filled emerald when favorited, outline otherwise. Click toggles via the mutation.
- **Project detail / work item detail / page detail** — same star toggle in the header.

### Empty state

When the user has no favorites, the rail shows: "Star a project, page, or work item to pin it here." Plain text, no CTA — there's nothing actionable from this view alone.

## Rollout & risk

- **Rollout**: same `/preview` implicit-flag approach. Nothing in the public dashboard navigates here.
- **Failure mode**: a regression in the entity-resolution check could let a user favorite something they can't see. **Mitigation**: every entity type has a dedicated `test_create_rejects_unreadable_entity` case (parametrised).
- **Kill criterion**: revertible by dropping the new submodule + the router mount. The `user_favorites` table stays — it's harmless on its own and other future surfaces (notifications, recents) may want it.

## Definition of Done

- 10 pytest tests pass against a real Postgres.
- mypy + ruff clean across the new submodule.
- Frontend tsc clean; the star toggle works end-to-end against a dev backend.
- PR description stamps the standard `feedback_pr_quality_checklist` template.

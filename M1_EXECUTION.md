# M1 — Demolition (scoped, file_sharing kept as transport)

Executable plan for milestone M1 of `RAPIDLY_ENGINEERING_SUITE_PLAN.md`,
revised 2026-05-21 after two scope decisions:

1. **Keep `file_sharing`** (P2P architecture intact, COTURN intact).
2. **Framing B:** file_sharing is *transport infrastructure*, not a
   top-level product surface. No "Files chamber" in the suite nav.
   Suite pitch leads with **Markup + Agents + 3D viewer**. file_sharing
   stays in code, has no headline nav entry, remains available as
   the underlying transport for Markup and as a niche "send live"
   handoff capability.

M1 removes the surfaces that don't fit an engineering audience and
renames the markup surface from `collab` to its real name. Five PRs.

**Read M0_EXECUTION.md first** — M1 assumes the no-attribution gate
is live, all `feat/projects-*` PRs are closed, and memory reflects
the engineering-suite pivot.

## Scope

| # | Branch | What goes | LOC out (est) |
|---|---|---|---|
| 1.0 | `feat/demo-demote-file-sharing-from-suite-nav` | UI-only: drop Files from suite nav per Framing B; backend untouched | ~0 net |
| 1.1 | `feat/demo-remove-media-chambers` | `sharing/{screen,watch,call}/` backend + frontend + flags + revolver chamber entries | ~3.6k |
| 1.2 | `feat/demo-remove-customer-portal` | `customers/` + `customers/customer_portal/` + customer-portal SDK package | ~6.5k |
| 1.3 | `feat/demo-remove-storefront` | `sharing/storefront/` + backend routes + frontend storefront pages | ~0.8k |
| 1.4 | `feat/demo-rename-collab-to-markup` | rename `sharing/collab/` → `sharing/markup/`, `components/Collab/` → `components/Markup/`, `/collab/*` routes → `/markup/*` | ~0 net |
| 1.5 | `feat/demo-trim-projects` | drop ~28 `projects/*` submodules, keep project/state/label/work_item/comment/activity | ~30k |

**Explicitly kept:**

- `sharing/file_sharing/` — entire backend chamber, P2P + WebRTC + signaling + share-link + COTURN. Reframed as **Files** in the engineering-suite UI.
- `catalog/share/` — dashboard-side entry point that creates file_sharing channels from catalog files. Kept because file_sharing is kept.
- `admin/file_sharing/` — HTMX admin surface for the kept chamber.
- `messaging/webhook/` handlers that fan out file_sharing events.
- `sharing/collab/` — kept under a new name (M1.4).
- `integrations/stripe/workers.py` file_sharing-related handlers — kept (workspace billing for kept Files surface).

## Conventions

- Shell snippets assume the repo root as `pwd`.
- Branches off freshly-pulled `main` after the prior M1 PR merges. **Do not** stack the M1 branches — the test suite must be valid at each tip on a clean main.
- Every PR runs locally before push: `cd server && uv run task lint && uv run task lint_types && uv run task test_fast` plus `cd clients && pnpm typecheck && pnpm lint`.
- Every PR stamps the Definition-of-Done block in §3.
- Tables are dropped with **new** Alembic migrations, never by deleting old migration files. `downgrade()` re-creates with the schema the latest pre-demolition migration left it in.
- Routes are unregistered in `server/rapidly/api.py` in the same PR that removes the module. No dead `include_router` calls between PRs.

---

## 1.0 — Demote file_sharing from suite nav (Framing B)

Branch: `feat/demo-demote-file-sharing-from-suite-nav`

### Scope (UI only, no backend deletes)

This is a small surgical PR before the larger demolitions. Removes
file_sharing's headline presence from the suite UI while keeping the
chamber intact in code.

- **Revolver landing** — remove any `<RevolverChamber kind="files">` or equivalent top-level Files entry from the suite's home page / dashboard nav.
- **Top-level routes** — `clients/apps/web/src/app/(authenticated)/file-sharing/` (the chamber's headline landing) gets either deleted or moved under `/(legacy)/file-sharing/` so the URL still resolves for existing users but no nav links point there.
- **Marketing copy** — any `Files` / `file-sharing` callout on the public landing pages comes out.
- **Dashboard sidebar** — kept entries: Markup, Agents (placeholder for now, lands in M4), Projects (the slim Coordination surface), Settings. Removed: any standalone "Files" entry.
- **`catalog/share/` UI** — keep the share-link generator on a per-file dropdown (`Share via live transfer`). It just isn't a top-level nav item.

### What stays untouched

- All backend code under `server/rapidly/sharing/file_sharing/`.
- All P2P + signaling + COTURN.
- Webhook + Stripe + admin/file_sharing — all kept.
- The share-link URL `/share/<slug>` still works (anonymous-receive flow stays live).

### Verify

```bash
cd clients/apps/web && pnpm typecheck && pnpm build
pnpm dev    # then click around: file-sharing chamber should not appear in any nav, but /share/<slug> should still work
```

Manual: send a file from a logged-in user to an anonymous receiver via `/share/<slug>`; confirm the P2P transfer completes.

### PR

Title: `feat(suite): demote file_sharing to transport infrastructure (Framing B)`. Body notes that no backend deletes happened; this is a nav/positioning change only.

---

## 1.1 — Remove media chambers (screen / watch / call)

Branch: `feat/demo-remove-media-chambers`

### Why first

Three small, structurally identical chambers. Each imports
`file_sharing` but nothing else imports *them*, so removal doesn't
cascade. Good warm-up before the bigger customer_portal PR.

### Surfaces

- Backend dirs: `server/rapidly/sharing/{screen,watch,call}/` — 12 files each.
- Models: `models/screen_*`, `models/watch_*`, `models/call_*`. Confirm with `git ls-files server/rapidly/models/ | grep -E '^.*models/(screen|watch|call)'`.
- Routes in `server/rapidly/api.py` lines 126, 128, 130 — remove `screen_router`, `watch_router`, `call_router` imports and `include_router` lines.
- Settings in `server/rapidly/config.py`: `FILE_SHARING_SCREEN_ENABLED`, `FILE_SHARING_WATCH_ENABLED`, `FILE_SHARING_CALL_ENABLED`. Remove the flags **and** any aliases.
- Frontend public env: `NEXT_PUBLIC_*` equivalents in `clients/apps/web/src/env.ts` (or whichever file declares them).
- Frontend pages: `clients/apps/web/src/app/(authenticated)/screen/`, `.../watch/`, `.../call/` plus any anonymous-flow variants.
- Frontend components: `clients/apps/web/src/components/{Screen,Watch,Call}/`.
- Frontend utils: `clients/apps/web/src/utils/{screen,watch,call}/`.
- Hooks: any `use{Screen,Watch,Call}Room` under `hooks/`.
- Tests: `server/tests/sharing/{screen,watch,call}/` and matching Playwright specs.
- Revolver landing: any `<RevolverChamber>` entries pointing at screen/watch/call.
- COTURN config: keep — file_sharing + markup still use it.

### DB migration

```bash
cd server
uv run alembic revision -m "drop screen watch call tables"
```

```python
def upgrade() -> None:
    op.drop_table("screen_sessions")
    op.drop_table("watch_rooms")
    op.drop_table("watch_room_members")
    op.drop_table("call_rooms")
    op.drop_table("call_room_members")
    # Confirm full list:
    #   grep -rh '__tablename__' rapidly/sharing/{screen,watch,call}

def downgrade() -> None:
    # Re-create each table with the column set the last pre-demolition
    # migration left it in. Copy from the latest add/alter for each.
    ...
```

### Steps

1. Delete the three backend directories.
2. Remove the model files. Drop their imports from `server/rapidly/models/__init__.py`.
3. Remove the three router imports + `include_router` lines in `api.py`.
4. Remove the three env flags from `config.py`.
5. Remove `NEXT_PUBLIC_*` from `env.ts`.
6. Delete the frontend directories listed above.
7. Walk typecheck errors: each one points at a former importer; remove.
8. Drop revolver chamber entries (in `components/Revolver/chambers.ts` or similar).
9. Write the migration.

### Verify

```bash
cd server
grep -rn -E "rapidly\.sharing\.(screen|watch|call)" rapidly --include="*.py" \
  | grep -v "rapidly/sharing/(screen|watch|call)/"
# expected: empty
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
uv run task test_fast
cd ../clients/apps/web && pnpm typecheck && pnpm build
```

---

## 1.2 — Remove `customers/` + customer-portal SDK

Branch: `feat/demo-remove-customer-portal`

### Why before storefront

storefront imports customer_portal. Drop the depended-on surface first.

### Anonymous-receive nuance

`customer_portal` exposed an anonymous-receive surface that wrapped
`file_sharing`. The kept `file_sharing` chamber has its own
share-link anonymous-receive flow — that lives in
`server/rapidly/sharing/file_sharing/` and stays. The wrapper goes.
If any code path **only** anonymous-receives via the customer_portal
wrapper (not the file_sharing share-link), that's a regression: audit
before deletion (see step 1 below).

### Surfaces

- Backend: `server/rapidly/customers/` in entirety (customer/, customer_portal/, customer_session/).
- Models: every model file under `models/` whose name starts with `customer`, `customer_portal_`, or `customer_session_`.
- Routes in `api.py` lines 137, 139, 141 (`customer_router`, `customer_session_router`, `customer_portal_router`).
- Email templates: any `customer_*.html` / `customer_*.j2` under `server/rapidly/messaging/email/templates/`.
- Frontend SDK package: `clients/packages/customer-portal/` in entirety. Drop the workspace entry from `pnpm-workspace.yaml`.
- Frontend dashboard routes consuming the SDK: `clients/apps/web/src/app/(authenticated)/dashboard/<workspace>/customers/`.
- Tests: `server/tests/customers/` in entirety.
- Stripe handlers: in `server/rapidly/integrations/stripe/workers.py`, any `customer_*` handlers (`customer.created`, `customer.subscription.*` if they fan out to customer_portal). Keep workspace-level Stripe handlers.
- Webhook event types tied to customers — enum entries in `messaging/webhook/types.py`. Shrink the enum in this PR's migration.
- OAuth2 scopes for customer reads/writes in `identity/auth/scope.py`. Remove.

### Pre-removal audit

Land first in this PR as a no-functional-change preamble:

```bash
cd server
grep -rn "from rapidly.customers" rapidly --include="*.py" \
  | grep -v "rapidly/customers/" | sort > /tmp/customer_importers.txt
cat /tmp/customer_importers.txt
```

Classify each line:
- **DOOMED** — importer is itself in this PR's delete-list. Will go.
- **KEPT** — importer stays. Decouple inline in this PR before deletion.
- **REGRESSION** — kept importer relies on functionality not available elsewhere. Stop. Surface to user before deleting.

Likely keepers needing decoupling: `messaging/notification`, `analytics/event`, `billing/payment`, `platform/workspace`.

### DB migration

```bash
uv run alembic revision -m "drop customers customer_portal customer_session tables"
```

Drop order: customer_session_* and customer_portal_* (FKs into customers) → customers. Migration also shrinks the webhook event enum (same pattern as M0's plan; see §1.2.1 below).

### 1.2.1 Webhook enum shrink

Postgres can't drop enum values directly. In the same migration:

```python
# Delete deliveries + subscriptions for doomed event types first.
op.execute(
    "DELETE FROM webhook_deliveries WHERE event_type IN "
    "('customer.created', 'customer.updated', 'customer.deleted', "
    " 'customer_portal.session_created', ...)"
)
op.execute(
    "DELETE FROM webhook_subscriptions WHERE event_type IN (...)"
)

# Then enum swap.
op.execute("CREATE TYPE webhook_event_type_new AS ENUM (...)")  # without dropped values
op.execute(
    "ALTER TABLE webhook_subscriptions "
    "ALTER COLUMN event_type TYPE webhook_event_type_new "
    "USING event_type::text::webhook_event_type_new"
)
op.execute("DROP TYPE webhook_event_type")
op.execute("ALTER TYPE webhook_event_type_new RENAME TO webhook_event_type")
```

Same for the matching `webhook_deliveries.event_type` column if it uses the enum (often duplicated; check).

Data loss is real: subscriptions and delivery history for those event types are gone. Call this out in the PR body and the deployment runbook.

### Steps

1. Land the audit. Decide per-importer: remove or decouple.
2. Decouple-first commits (no functional change).
3. Delete the customer directories.
4. Drop the SDK package from `pnpm-workspace.yaml` and remove `clients/packages/customer-portal/`.
5. Remove routes from `api.py`.
6. Remove scopes from `identity/auth/scope.py`. Update `oauth2/well_known.py` (or wherever scopes are exported) so the OAuth surface doesn't advertise gone scopes.
7. Write the migration (drops + enum shrink + deletes).
8. Add `clients/apps/web/middleware.ts` redirect: any old `/customers/*` URL 301s to `/dashboard/`.

### Verify

```bash
cd server
grep -rn "Customer\|customer_portal\|customer_session" rapidly --include="*.py" \
  | grep -v "# kept:" | head -20
# expected: nothing meaningful — kept references annotated with "# kept:"
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
uv run task test_fast
cd ../clients/apps/web && pnpm typecheck && pnpm build
```

Manual: send a file via `file_sharing` share-link to a fresh browser session. Anonymous-receive must still work. If it doesn't, the customer_portal wrapper was load-bearing — roll back this PR and re-audit.

---

## 1.3 — Remove storefront

Branch: `feat/demo-remove-storefront`

### Surfaces

- Backend: `server/rapidly/sharing/storefront/` — 10 files.
- Models: `models/storefront*`.
- Routes in `api.py` line 115 (`storefront_router`).
- Frontend storefront pages — 4 files under `clients/apps/web/src/app/(unauthenticated)/` (likely).
- Frontend components under `clients/apps/web/src/components/Storefront/`.
- Marketing landing-page sections that name "storefront" as a feature — these need editorial review, not just deletion. Coordinate with anyone owning the marketing copy.

### DB migration

```bash
uv run alembic revision -m "drop storefront tables"
```

### Steps + Verify

Mechanical. Same pattern as 1.1. Storefront has no other importers
once customers is gone.

---

## 1.4 — Rename `collab` → `markup`

Branch: `feat/demo-rename-collab-to-markup`

### Why now (before projects-trim)

Pure rename. Touch every Collab import site once, then leave the
file-shaped surface alone. Easier to do in isolation than in the
middle of the larger projects-trim PR.

### Surfaces

- Backend dir: `git mv server/rapidly/sharing/collab/ server/rapidly/sharing/markup/`.
- Python imports: `from rapidly.sharing.collab` → `from rapidly.sharing.markup`. Script: `grep -rl "rapidly.sharing.collab" server/ | xargs sed -i 's/rapidly\.sharing\.collab/rapidly.sharing.markup/g'`. Re-grep for any stragglers.
- Routes: change the prefix in `markup/api.py` from `/collab` to `/markup`. Match scope names if any reference collab.
- Env flags: `FILE_SHARING_COLLAB_ENABLED` → `MARKUP_ENABLED`. `NEXT_PUBLIC_COLLAB_E2EE` → `NEXT_PUBLIC_MARKUP_E2EE`. Update `config.py` and `env.ts`.
- Frontend dirs: `git mv clients/apps/web/src/components/Collab clients/apps/web/src/components/Markup`; `git mv clients/apps/web/src/utils/collab clients/apps/web/src/utils/markup`; rename `hooks/useCollab*` per file.
- Frontend routes: `clients/apps/web/src/app/.../collab/` → `.../markup/`. Add a 301 in `middleware.ts` for the old path.
- Frontend imports: `grep -rl -E "Collab|collab" clients/apps/web/src --include='*.ts' --include='*.tsx' | xargs sed -i ...`. Manual review for casing edge cases (`isCollab`, `CollabState`, etc.).
- Memory entries: rename "Collab chamber" → "Markup chamber" where they refer to the surface. **Don't** rewrite history entries that describe the original name; those stay accurate as history.

### Table-rename decision

Two options. **Recommend (b):**

(a) Rename `collab_*` → `markup_*` tables in a migration. Cleaner long-term, ugly to write.
(b) Leave the tables `collab_*`, only rename the Python references. Tables aren't user-visible; the naming drift is acceptable.

If (b): `__tablename__ = "collab_state"  # historical name; surface is now Markup` on each model.

### Verify

```bash
cd server
grep -rn -E "\\bcollab\\b" rapidly --include="*.py" | grep -v "collab_state\|# historical"
# expected: empty
uv run task lint && uv run task lint_types && uv run task test_fast

cd ../clients/apps/web
grep -rn -E "Collab|collab" src --include="*.ts" --include="*.tsx" | head
# expected: nothing in surface code (test fixtures with "collab" in a string literal are fine if there are any)
pnpm typecheck && pnpm build && pnpm test
```

Smoke test: open `/markup/` in two browsers, draw, confirm strokes sync.

---

## 1.5 — Trim `projects/`

Branch: `feat/demo-trim-projects`

### Keep-list

Keep exactly six submodules under `server/rapidly/projects/`:

```
project, state, label, work_item, comment, activity
```

Plus `common.py` if it contains shared infra used by the kept six (audit: `head -30 server/rapidly/projects/common.py`).

### Drop-list (everything else)

```
analytic_view, attachment, cycle, deploy_board, estimate, external_link,
favorite, intake, link, member, member_invite, mention, module,
module_extras, page, reaction, recent_visit, resource_user_property,
sticky, subscriber, user_property, view, vote, work_item_type
```

24 directories.

### Surfaces

Per dropped submodule:

- Backend directory under `server/rapidly/projects/`.
- Models for that submodule under `server/rapidly/models/`.
- Routes in `api.py` lines 180–202 — every line referencing a dropped submodule's router goes; every line referencing a kept submodule survives.
- Tests under `server/tests/projects/<submodule>/`.
- Frontend dashboard pages under `clients/apps/web/src/app/.../projects/` that consume dropped surfaces (cycle pages, module pages, sticky widgets, deploy-board, intake form, etc.).
- Frontend hooks under `clients/apps/web/src/hooks/projects/` for each dropped submodule.
- Frontend types in `clients/packages/client/` — regenerated from the new OpenAPI spec.

### DB migration

```bash
uv run alembic revision -m "drop projects extension tables (cycle, module, analytic_view, deploy_board, ...)"
```

Largest migration in M1 — ~25 tables. Drop order matters (child tables first to satisfy FK constraints). Build the order manually from the keep/drop inventory; **don't trust autogenerate** for cross-submodule FK order.

`downgrade()` recreates in reverse order. Acceptable to ship a `pass` downgrade with a note "rollback requires restoring from backup; data is gone after upgrade" — call it out in the PR body. Engineering precedent on this codebase is to write the full downgrade, so prefer that unless the cost is genuinely prohibitive.

### Steps

1. **Export the current OpenAPI spec as baseline:** `uv run task openapi_export`. Save the resulting file to `/tmp/openapi-pre-trim.json`. Used for diff-review of the codegen output.
2. Delete the drop-list directories. Script it from the inventory above so nothing is missed.
3. Drop routes from `api.py`. The remaining `projects/` router list should be exactly six lines.
4. Drop models from `server/rapidly/models/`. Remove imports from `models/__init__.py`.
5. Write the migration. Order: leaves first (e.g., `module_extras`, `cycle_user_properties`) then parents (`cycle`, `module`) then any remaining.
6. Regenerate the client: `uv run task openapi_export && cd clients/packages/client && pnpm generate`. Diff `/tmp/openapi-pre-trim.json` vs the new spec — expect ~25 schema removals and ~80 operation removals.
7. Frontend typecheck will burst with hundreds of errors. Walk it: each error names a gone type → remove the importer.
8. Update the `/dashboard/<workspace>/projects/<id>/` page to render only the kept tabs.
9. End-to-end sanity: create a project, add state + label + work_item + comment + activity row, render the page.

### Verify

```bash
cd server
grep -rn -E "from rapidly.projects.(cycle|module|deploy_board|intake|analytic_view|sticky|vote|recent_visit|mention|view|user_property|favorite|external_link|attachment|subscriber|reaction|work_item_type|member|member_invite|module_extras|resource_user_property|link|page|estimate)" rapidly --include="*.py"
# expected: empty
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
uv run task test
cd ../clients/apps/web && pnpm typecheck && pnpm build && pnpm test
```

Open `/dashboard/<workspace>/projects/<some-project>/` and confirm only the kept surfaces render.

---

## 2. Acceptance for M1 as a whole

After 1.1 through 1.5 all merge:

- [ ] **No dead routes.** `grep -cE "include_router" server/rapidly/api.py` matches the kept-domain count.
- [ ] **No dead imports of demolished modules.** `grep -rn -E "rapidly\.sharing\.(screen|watch|call|storefront)|rapidly\.customers" server/rapidly | wc -l` returns 0.
- [ ] **file_sharing still works.** Open `/share/<slug>` in two browsers; one uploads, the other downloads via P2P. Confirm COTURN relay also still works (Chrome devtools → Issues panel → no ICE failures behind a NAT).
- [ ] **Markup chamber still works.** Open `/markup/` (new path) in two browsers, draw a stroke, see it sync.
- [ ] **Frontend builds.** `cd clients/apps/web && pnpm typecheck && pnpm build` exit 0.
- [ ] **Backend tests green.** `cd server && uv run task test` exit 0.
- [ ] **No-attribution gate green** on every M1 PR.
- [ ] **Migrations chain cleanly.** `uv run alembic upgrade head && uv run alembic downgrade base && uv run alembic upgrade head` round-trips.
- [ ] **No name-drift.** No file/component called `FileSharing` was left on disk by accident (kept name is just "file_sharing" / "Files"). Spot-check via `grep -rn "FileSharing" clients/apps/web/src`.
- [ ] **Memory updated.** New `project_m1_demolition_complete.md` written; obsolete chamber-status entries (Screen, Watch, Call) annotated `[CHAMBER REMOVED 2026-MM-DD — historical]`. The Collab entry annotated `[SURFACE RENAMED → markup 2026-MM-DD]` (keep the historical content; just add the rename note).

---

## 3. Per-PR Definition of Done (M1 flavor)

Every demolition PR adds this block to its description (per the
per-PR quality memory):

```markdown
## Definition of Done — M1 demolition

### Surface removed (or renamed)
- Backend: <dirs deleted / renamed>
- Models: <models removed>
- Routes: <api.py lines removed>
- Frontend: <dirs deleted / renamed>
- Tests: <test dirs deleted>
- Settings/flags: <env vars removed>
- Migration: <new migration filename>

### Verification
- [ ] `uv run task lint` green
- [ ] `uv run task lint_types` green
- [ ] `uv run task test_fast` green
- [ ] `pnpm typecheck && pnpm build` green
- [ ] `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` round-trips
- [ ] No-attribution `scan` job green
- [ ] OpenAPI client regenerated if routes changed
- [ ] Manual: hit one kept route adjacent to the demolition (sanity)
- [ ] Manual: file_sharing P2P still works (every M1 PR — file_sharing is load-bearing now)

### Audit
- [ ] No kept module imports from the deleted module (`grep` reported)
- [ ] No env flag named after the deleted module remains
- [ ] No nav entry / revolver chamber pointing at the deleted surface
```

---

## 4. Rollback

Each M1 PR is its own commit on main. Rollback by:

1. `gh pr create` a revert PR.
2. Re-run the migration's `downgrade()` first if data needs to come back. `downgrade()` only restores schema; data is gone.
3. No-attribution gate runs unchanged on revert PRs.

Data loss is irreversible: rows in dropped tables (webhook subscriptions for dead event types, customer records, etc.) are gone the moment the migration upgrades. Call this out in each PR body and in the deployment runbook.

---

## 5. After M1

`MEMORY.md` updates at the end of M1:

- Add: `[M1 demolition complete (YYYY-MM-DD)](project_m1_demolition_complete.md)` with body summarizing the new shape (Files + Markup + slim Projects + Identity + Workspace + Billing + Catalog + Messaging + Analytics).
- Annotate as `[CHAMBER REMOVED 2026-MM-DD — historical]`:
  - `project_phase_b_complete.md` (Screen)
  - `project_phase_c_d_progress.md` (Watch + Call)
- Annotate `project_phase_e_progress.md` as `[SURFACE RENAMED → markup 2026-MM-DD]`. Keep the historical content as the Markup origin story.
- The `project_engineering_suite_pivot.md` entry stays current — it was written for this milestone sequence.

Next milestone: **M2 — Engineering primitives.** Adds versioning + ACL on the kept Files chamber (the durable-storage augmentation we discussed), PdfUnderlayElement and ImageUnderlayElement in Markup, PDF rendering via `pdfjs-dist`, and the scale-calibration tool with engineering-units dimension overlay. Plan in `M2_EXECUTION.md` on user go-ahead.

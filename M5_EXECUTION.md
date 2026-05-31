# M5 — Agent runtime UI

Executable plan for milestone M5 of `RAPIDLY_ENGINEERING_SUITE_PLAN.md`.
M5 ships the frontend of the Agents chamber on top of the M4 backend:
graph editor, node palette, properties panels, run tab, eval tab,
deploy tab, and realtime multi-user editing via Yjs+E2EE.

**Read M4 first.** M5 binds against the routes and types M4 ships.
If M4.1 (domain scaffold) isn't on main, M5.1 can't start.

## Scope decisions (locked)

- **Graph editor: `@xyflow/react`** (MIT, ~250 kB gz). The strategic plan's recommendation; satisfies the "self-hosted, OSS-licensed" policy.
- **Realtime collab on the graph: Yjs + the existing E2EE provider.** Reuses the markup chamber's transport. No new infrastructure.
- **No AI features in the UI itself** — per the no-AI-in-other-chambers memory, the agents chamber is the *only* place AI features live, but those features are the *workflows the user builds*, not the editor experience. Skip "AI suggest a node," "AI auto-arrange," etc.
- **Clean-room compliance carries from M4** — every component reads as native Rapidly, not a port.

## Scope (7 PRs, ~3 weeks)

| # | Branch | What |
|---|---|---|
| 5.1 | `feat/agents-ui-scaffold` | `/dashboard/[workspace]/agents/` route; workflow list; sidebar entry; empty xyflow canvas |
| 5.2 | `feat/agents-ui-graph-editor` | Node placement, edge drawing, undo/redo, single-user version save |
| 5.3 | `feat/agents-ui-node-config` | Node palette (categories: I/O, Logic, LLM, Tools, Construction-placeholder); per-node-type properties panel |
| 5.4 | `feat/agents-ui-run-tab` | Trigger button + live trace via SSE; per-node input/output viewer; cancel button |
| 5.5 | `feat/agents-ui-eval-tab` | Dataset picker + eval run launcher; metric display + per-row breakdown |
| 5.6 | `feat/agents-ui-deploy-tab` | Schedule (cron), webhook trigger, workspace API key issuance for run-trigger scope |
| 5.7 | `feat/agents-ui-realtime-collab` | Yjs provider on the graph; presence cursors; conflict-free multi-edit |

Each PR ships with its own Playwright spec + stamps the per-PR DoD (§5).

## Conventions

- Shell snippets assume the repo root as `pwd`.
- Branches off freshly-pulled `main`. Do not stack.
- Pre-push: `cd clients/apps/web && pnpm typecheck && pnpm lint && pnpm test && pnpm playwright test agents-<spec>.spec.ts`.
- Backend `cd server && uv run task test_fast` is still required even when only frontend changes — the OpenAPI client regen check catches drift.
- Per-PR DoD in §5.

---

## 5.1 — Chamber scaffold

Branch: `feat/agents-ui-scaffold`

### Goal

Click "Agents" in the dashboard sidebar → land on a workflows list →
click a workflow → see an empty xyflow canvas with placeholder
nodes. No editing yet; just routing and bones.

### Frontend additions

- **Deps:** `cd clients/apps/web && pnpm add @xyflow/react`. Pin to latest 12.x.
- **Routes** under `clients/apps/web/src/app/(main)/dashboard/[workspace]/agents/`:
  - `page.tsx` — workflows list (paginated, filterable by project_id, search by name)
  - `[workflowId]/page.tsx` — single workflow → renders editor shell
  - `[workflowId]/runs/page.tsx` — recent runs tab
  - `[workflowId]/evals/page.tsx` — evals tab
  - `[workflowId]/deploy/page.tsx` — deploy tab
- **Components** under `clients/apps/web/src/components/Agents/`:
  ```
  Agents/
  ├── WorkflowList.tsx
  ├── NewWorkflowDialog.tsx
  ├── Editor/
  │   ├── EditorShell.tsx          # header + tabs (Editor / Runs / Evals / Deploy)
  │   ├── EditorCanvas.tsx         # xyflow mount; deferred-loaded
  │   └── EditorCanvasFallback.tsx
  └── EmptyState.tsx
  ```
- **Hooks** under `clients/apps/web/src/hooks/agents/`:
  ```
  useWorkflowList.ts
  useWorkflow.ts
  useCreateWorkflow.ts
  useUpdateWorkflow.ts
  useDeleteWorkflow.ts
  ```
- **Sidebar entry.** Add an "Agents" item to `clients/apps/web/src/components/Layout/Dashboard/DashboardSidebar.tsx`. Icon: `Bot` from `lucide-react`. Order: between "Markup" and "Projects".
- **xyflow lazy load.** The library is ~250 kB gz. Use `next/dynamic` so other chambers don't pay:
  ```ts
  const EditorCanvas = dynamic(() => import('@/components/Agents/Editor/EditorCanvas'), {
    ssr: false,
    loading: () => <EditorCanvasFallback />,
  })
  ```

### Tests

- Workflow list pagination + create dialog (msw mocks).
- Empty state for a fresh workflow with no graph.
- Sidebar entry presence (snapshot or query).
- Playwright `agents-scaffold.spec.ts`: navigate sidebar → agents → list → click "New workflow" → see empty editor.

### Verify

```bash
cd clients/apps/web
pnpm typecheck && pnpm lint && pnpm test
pnpm playwright test agents-scaffold.spec.ts
pnpm build  # main bundle should NOT grow by 250 kB (xyflow lazy)
cd ../../server && uv run task test_fast && uv run task openapi_export
```

---

## 5.2 — Graph editor (single user)

Branch: `feat/agents-ui-graph-editor`

### Goal

Place nodes by dragging from a palette, draw edges between handles,
undo/redo, save as a new `WorkflowVersion` via `POST /api/workflows/{id}/versions`.
Single-user only; multi-user collab is M5.7.

### Behaviours

- **Drag node from palette → drop on canvas.** Creates a node with default config for that node_type. The palette ships with three categories for now: I/O (Trigger, End), Logic (Branch, Loop), Echo (placeholder until M5.3 wires the real palette).
- **Draw an edge** by dragging from an output handle to an input handle. Multi-output (Branch) and multi-input nodes supported via named handles.
- **Selection + delete.** Click to select; Backspace/Delete removes.
- **Undo/redo.** Local stack, 100-entry deep. Doesn't survive reload (deliberate — the published version is the source of truth).
- **Save published version.** Header has "Publish" button. Posts the current `graph_json` to `POST /api/workflows/{id}/versions`; on success, surfaces a toast and updates `currentVersionId`.
- **Validation.** Before publish: assert no cycles, no orphan nodes (every non-trigger node reachable from the trigger), no edges with mismatched type expectations. Block publish with a clear error if any fail.

### Graph schema

```ts
// types/agents/graph.ts
interface AgentGraph {
  nodes: AgentNode[]
  edges: AgentEdge[]
}
interface AgentNode {
  id: string                  // ulid
  type: string                // 'http' | 'llm' | 'branch' | ...
  position: { x: number, y: number }
  config: Record<string, unknown>   // per-type, validated by Zod schema in M5.3
}
interface AgentEdge {
  id: string
  source: string              // source node id
  sourceHandle?: string       // for multi-output
  target: string
  targetHandle?: string       // for multi-input
}
```

This shape matches what M4's `WorkflowVersion.graph_json` accepts.

### Tests

- Drag-drop unit test (xyflow's `useReactFlow` mocked).
- Edge creation between handles.
- Cycle detection (3-node cycle rejected).
- Orphan detection (a node disconnected from the trigger rejected).
- Undo/redo invariants.
- Publish posts the right payload + receives version_number back.

### Verify

```bash
pnpm playwright test agents-editor.spec.ts
```

Manual: build a 3-node workflow (Trigger → Echo → End), publish, reload page, confirm the graph is still there.

---

## 5.3 — Node palette + properties panels

Branch: `feat/agents-ui-node-config`

### Goal

Real node palette covering every node type M4 ships. Per-node-type
properties panel on the right showing config form, with Zod
validation.

### Palette structure

```
Triggers          # surfaces that start a run
  - Manual trigger
  - Webhook trigger          (uses M5.6 endpoint)
  - Schedule trigger         (uses M5.6 cron)

I/O
  - File read
  - File write
  - End (terminal output)

Logic
  - Branch                   # CEL condition
  - Loop                     # iterate body subgraph
  - Sub-workflow

LLM
  - LLM call
  - Structured output

Tools
  - HTTP call
  - Code (sandboxed)
  - RAG search

Coordination
  - Human-in-loop

Construction                 # placeholder until M6
  - (empty — coming in M6)
```

### Properties panel

Per node type, a form component under
`clients/apps/web/src/components/Agents/Editor/NodeConfigs/`:

```
NodeConfigs/
├── HttpNodeConfig.tsx       # url, method, headers, body, timeout
├── LlmNodeConfig.tsx        # provider, model, prompt template, temperature, system_prompt
├── StructuredOutputConfig.tsx
├── BranchNodeConfig.tsx     # CEL expression with monaco-yaml-like highlighting (or just a plain textarea v1)
├── LoopNodeConfig.tsx
├── CodeNodeConfig.tsx       # monaco-editor python
├── RagSearchNodeConfig.tsx  # collection picker + k
├── HumanInLoopConfig.tsx    # recipient picker, prompt, response_schema (JSON Schema mini-editor)
├── SubWorkflowConfig.tsx    # workflow picker + version pin
├── FileReadConfig.tsx
├── FileWriteConfig.tsx
└── _registry.ts             # map node_type → config component
```

Each config has a Zod schema. The panel runs validation on every
keystroke; invalid forms block publish.

### Code editor inside config

For Code node (CodeNodeConfig.tsx): use `@monaco-editor/react`
(lazy-loaded, ~1 MB gz). Set language to Python. Only mounts when
the user actually selects a Code node — most users will never load
monaco.

### Schema validation

`clients/apps/web/src/lib/agents/schemas.ts` holds Zod schemas
mirroring the backend Pydantic types. Drift between frontend Zod and
backend Pydantic is a recurring class of bugs; the openapi
codegen-typed signatures help, but Zod is the runtime guard.
Acceptance criterion: every node_type's config has a Zod schema +
its corresponding Pydantic model.

### Tests

- Each NodeConfig form: required-field validation, invalid-value rejection.
- Registry coverage: assert every node_type from the backend has a config component (loop over the OpenAPI-generated enum).
- CEL syntax highlighting (light-touch test: assert the textarea takes input; full grammar is not in scope).
- Code editor lazy-load: confirm monaco's chunk is not in the main bundle.

### Verify

Manual: build a workflow that uses each node type at least once. Publish. Confirm validation catches an empty URL on HTTP node, an empty prompt on LLM node, etc.

---

## 5.4 — Run tab + live trace

Branch: `feat/agents-ui-run-tab`

### Goal

"Runs" tab on a workflow shows recent runs (paginated). Click one →
left panel shows the graph (read-only, with status overlay per
node); right panel shows the selected NodeRun's input/output/error.
Live runs stream their trace via SSE so the engineer sees nodes
light up in real time.

### Surfaces

- `[workflowId]/runs/page.tsx` — list of runs (status, started_at, duration, triggered_by).
- `[workflowId]/runs/[runId]/page.tsx` — split view:
  - Left: read-only graph with per-node status badges (pending / running / succeeded / failed / skipped / awaiting_human). Colors match the markup chamber's existing palette.
  - Right top: run-level info (status, input, output, error_message if failed).
  - Right bottom: NodeRun inspector for the clicked node — its input_data, output_data, error_message, started_at, completed_at, duration.
- **Trigger button** on the editor page → modal asking for input_data (JSON or a generated form based on the trigger node's input schema if present) → starts a run → navigates to `runs/[newRunId]`.
- **Cancel button** on a running run.

### SSE binding

Backend already exposes `analytics/eventstream`. Add a thin hook
`useRunTrace(runId)` that:

1. Opens `EventSource('/api/runs/{runId}/trace')` (backend endpoint exists from M4.2).
2. Filters to events matching `runId`.
3. Reduces into a `Map<nodeId, NodeRunState>`.
4. Closes the connection when the component unmounts or the run reaches a terminal state.

Reconnection: on dropped connection, exponential backoff up to 30 s; show a "reconnecting" badge in the UI.

### Tests

- Run list pagination + sort (status, started_at).
- Run detail page: per-node status badges match the run state.
- Trace SSE hook: synthetic event stream → state updates match.
- Trigger modal: invalid input rejected; valid input starts a run and navigates.
- Cancel button: only enabled when status is `running` or `pending`.

### Verify

Manual: build a workflow with a 5-second sleep (Code node) + an LLM call, trigger it, watch the nodes light up in sequence, confirm the LLM node's output displays as soon as it completes.

---

## 5.5 — Eval tab

Branch: `feat/agents-ui-eval-tab`

### Goal

Workspace-level Datasets list + a workflow's Evals tab where you
pick a dataset, kick off an eval run, watch progress, and review
metrics + per-row results.

### Surfaces

- `/dashboard/[workspace]/agents/datasets/` — workspace dataset list (separate from per-workflow routes).
- `/dashboard/[workspace]/agents/datasets/[datasetId]/` — dataset detail; CSV upload to populate rows; preview.
- `/dashboard/[workspace]/agents/[workflowId]/evals/page.tsx` — list of past eval runs.
- `/dashboard/[workspace]/agents/[workflowId]/evals/[evalId]/page.tsx` — eval detail:
  - Metric cards: pass_rate, avg_latency_ms, total_cost_usd.
  - Per-row table: row_index, expected_output, actual_output, score, latency.
  - Diff view on click: side-by-side JSON diff between expected and actual.

### CSV upload

A dataset's schema_json defines input + expected_output shapes. CSV
upload maps columns by name. Frontend validates that every required
input/output column exists before submission. Reject the file with a
useful error otherwise; don't fail mid-row.

### Eval launcher

"Run eval" button on the workflow's evals tab → modal asking for
dataset_id + workflow_version_id (default: current version) → posts
to `POST /api/eval-runs` (backend endpoint from M4.8) → navigates to
`evals/[newEvalId]` where progress streams via SSE.

### Tests

- Dataset CRUD via mocked client.
- CSV parsing + validation; missing-column error.
- Eval run launcher + status polling (or SSE if backend supports streaming eval progress).
- Per-row diff view rendering.

### Verify

Manual: create a 5-row dataset for an LLM extraction workflow, run an eval, inspect pass_rate and one of the per-row diffs.

---

## 5.6 — Deploy tab

Branch: `feat/agents-ui-deploy-tab`

### Goal

Three ways to trigger a workflow without clicking the manual
"Trigger" button:

- **Schedule** — cron expression; runs the workflow on schedule with empty input or a configured input template.
- **Webhook** — system-generated URL with a token; POST body becomes the run's input_data; signature verification optional.
- **Workspace API key** — issues a scoped key with `runs_trigger` scope only (separate from `workflows_write`). The key lets external systems start runs via `POST /api/workflows/{id}/runs`.

### Backend additions in this PR

Most of the surface exists from M4 + existing workspace API tokens.
New endpoints to land in this PR:

```
POST   /api/workflows/{id}/schedules           cron expression, enabled bool, input_template JSON
GET    /api/workflows/{id}/schedules
DELETE /api/workflows/{id}/schedules/{sid}

POST   /api/workflows/{id}/webhooks            issue webhook; returns URL + signing secret (one-shot)
GET    /api/workflows/{id}/webhooks
DELETE /api/workflows/{id}/webhooks/{whid}
```

`Schedule` and `WebhookTrigger` ORM rows added under
`server/rapidly/agents/trigger/`. Migration in this PR.

### Schedule worker

Dramatiq has a `CronTrigger` pattern already used elsewhere in the
codebase (see `server/rapidly/identity/auth/workers.py:6`). New
worker `agents/trigger/workers.py:tick_schedule_worker` runs every
minute, queries due schedules, starts runs.

### Webhook handler

`POST /api/webhooks/agent/{token}` — public endpoint (rate-limited).
Validates token; loads the associated workflow; starts a run with
the request body as input_data. If a signing secret is configured,
verifies the `X-Rapidly-Signature` HMAC header.

### Frontend

`[workflowId]/deploy/page.tsx` with three tabs:

- Schedules — table + add/edit form + cron-expression preview (using `cron-parser`).
- Webhooks — table; "Create webhook" reveals URL + signing secret once with a copy-to-clipboard button; rotation flow.
- API key — "Issue key" reveals once with copy-to-clipboard; lists existing keys with last-used timestamps.

### Tests

- Cron-expression preview validity.
- Webhook one-shot reveal (closing the modal forgets the secret; reload doesn't redisplay it).
- Signature verification on webhook POSTs.
- API key scope limitation: a `runs_trigger`-only key cannot edit the workflow (`POST /api/workflows/{id}/versions` → 403).

### Verify

Manual: schedule a workflow for `* * * * *` (every minute) with a 5-second sleep, watch a run appear in the runs list at the next minute boundary. Then issue a webhook, POST to it via `curl`, confirm a run starts.

---

## 5.7 — Realtime collab on the graph

Branch: `feat/agents-ui-realtime-collab`

### Goal

Multiple users on the same workflow editor see each other's nodes,
edges, and cursors in real time. CRDT-backed so simultaneous edits
don't clobber. Reuses the markup chamber's Yjs + E2EE provider.

### Architecture

- The workflow's *draft* (between published versions) lives in a Yjs document under a `Y.Map` keyed `nodes` and `edges`. Each node is a `Y.Map<field, value>`; each edge is a `Y.Map<field, value>`.
- On editor mount: open a Yjs provider against `/v1/markup-signaling/agents-<workflowId>` (reuse the markup signaling endpoint with a workflow-scoped room id).
- On any local edit (node added, moved, deleted; edge added, deleted): mutate the Yjs map; the provider broadcasts.
- On any remote change: xyflow re-renders.
- On publish: serialize the Yjs document to `graph_json` and POST as a new version.

### Why reuse markup signaling

The existing markup provider already handles E2EE, room auth via
first-message body, signaling envelope cap, replay protection, rate
limiting, and reconnection. Building a parallel signaling path would
duplicate ~3,000 LOC of tested infrastructure.

Trade-off: the markup signaling is designed for whiteboard sessions,
which are ephemeral and high-throughput. Agent-graph editing is
persistent + low-throughput. Mismatched profile, but functional. v2
can split.

### Presence

Yjs awareness API → broadcast each user's cursor position +
selected node id. Render other users' cursors with their workspace-
member name + a deterministic color per user.

### Conflict semantics

Yjs gives us automatic CRDT merge. Specific behaviours:

- **Moving the same node from two clients:** last-writer-wins on the position field (Yjs map semantics).
- **Both delete the same node:** idempotent.
- **One deletes, one edits:** delete wins (the edit is silently lost — Yjs map field set on a deleted key).
- **Both add an edge between the same pair of nodes:** two edges exist (different ids). Add a normalization step on save that dedups.

### Sync state indicator

Small badge: green "synced" / yellow "syncing" / red "disconnected".
Click to see peer list + last-sync timestamp.

### Tests

- Two-client integration test: client A adds a node; client B sees it within 200 ms.
- Concurrent move of same node: final position matches Yjs's tie-breaker.
- Delete-vs-edit race: deletion wins.
- Publish serializes the Yjs document into a clean `graph_json` payload.

### Verify

Manual: open the same workflow in two browser windows, edit on both, confirm convergence + cursor presence + sync badge state.

---

## 5.A — Acceptance for M5 as a whole

After 5.1–5.7 land:

- [ ] **Agents chamber lives at `/dashboard/[workspace]/agents/`** with a sidebar entry.
- [ ] **Workflow CRUD via UI** — list, create, rename, archive, delete.
- [ ] **Graph editor end-to-end** — drag, connect, configure, publish version.
- [ ] **Every M4 node type has a UI config component** with Zod validation.
- [ ] **Run tab shows live progress via SSE** — nodes light up; cancel works.
- [ ] **Eval tab + dataset CRUD work** — CSV import, run, metric display, per-row diff.
- [ ] **Deploy tab covers schedule, webhook, API key.**
- [ ] **Realtime collab on the graph works** — two users edit simultaneously, no data loss.
- [ ] **No-attribution `scan` job green on every M5 PR.**
- [ ] **Bundle audit:** main bundle has not grown by more than 100 kB net across all of M5; xyflow and monaco are both lazy-loaded.
- [ ] **Memory updated.** `project_m5_agent_ui_complete.md` written; pivot memory's Agents-chamber line moves from `[BACKEND LANDED]` to `[FULL CHAMBER LIVE]`.

---

## 5. Per-PR Definition of Done (M5 flavor)

```markdown
## Definition of Done — M5 agent UI

### Surface added
- Routes / components / hooks: <list>
- New deps: <package@version or none>
- Backend touches (if any): <files, migration name>

### Verification
- [ ] `pnpm typecheck && pnpm lint && pnpm test` green
- [ ] `pnpm playwright test <new spec>` green
- [ ] `cd server && uv run task test_fast && uv run task openapi_export` green
- [ ] No-attribution `scan` job green
- [ ] Bundle delta on main: <X kB>. Lazy-loaded surfaces don't count against main.
- [ ] Manual: end-to-end exercise of the new surface

### Clean-room compliance
- [ ] No upstream UI patterns copied; the editor reads as a Rapidly component
- [ ] Component names don't echo the upstream's component names
- [ ] Reviewer confirms: "Looks and feels like the rest of Rapidly"

### A11y + UX
- [ ] Keyboard nav works for the new surface (Tab + Enter; canvas-specific Delete/Backspace)
- [ ] Focus rings visible
- [ ] Empty / loading / error states all present for any data fetch
```

---

## 6. Rollback

Each M5 PR is its own commit on main. Frontend reverts are clean —
deleted components and routes simply 404 after revert. Backend
additions in 5.6 (schedules + webhook triggers tables) revert with
the migration's `downgrade()` — rows are lost. Issued API keys via
the existing workspace token system survive a revert as long as the
token table isn't touched.

---

## 7. After M5

`MEMORY.md` updates:

- Add `[M5 agent UI complete (YYYY-MM-DD)](project_m5_agent_ui_complete.md)`. Body: notes the lazy-load architecture, the Yjs reuse for realtime collab, the per-node Zod-schema validation pattern.
- Annotate the pivot memory's Agents-chamber line: `[FULL CHAMBER LIVE 2026-MM-DD]`.

Next milestone: **M6 — Construction nodes + canonical workflows
(3 weeks).** Adds the engineering-specific nodes (clash detection
on a federated model via IfcOpenShell, RFI draft, deliverable check,
discipline-lead notify) plus four shippable starter workflows
(daily clash sweep, deliverable submission, site walk → punch list,
drawing change log). Lands the Coordination chamber's real `Clash`,
`Rfi`, `Approval`, `Deliverable` entities — until then, M3.6's pin
labels stay free-form. Plan in `M6_EXECUTION.md` on user go-ahead.

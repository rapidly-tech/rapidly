# Rapidly — Engineering Suite Plan

**Status:** Draft v1 · 2026-05-21 · local-only, gitignored (mirrors `COLLAB_WHITEBOARD_PLAN.md`)
**Scope:** Pivot Rapidly into a unified engineering suite — markup + agent builder + coordination + documents — and use the agent builder as the substrate for an agentic reimagining of construction-deliverable workflows.
**Brand:** Rapidly stays.
**Operating rule:** The agent-builder subsystem is a **clean-room rewrite** of a public open-source design. No attribution to the upstream anywhere in code, comments, docs, commits, branch names, or UI. The grep gate in §10 enforces this in CI.

---

## 0. Executive summary

We're converging Rapidly's existing FastAPI + Next.js stack on a single product: an **engineering suite** with four user-visible chambers:

1. **Markup** — collaborative redlines on PDFs, drawings, and 3D models (IFC / NWD via self-hosted viewer)
2. **Agents** — visual workflow builder, runs, evaluations, traces
3. **Coordination** — work items, deliverables, approvals, RFIs
4. **Documents** — uploads, versions, controlled access

The infrastructure layer (auth, workspaces, billing, messaging, S3, Redis, Postgres, Hetzner deploy) is reused without changes. The product layer is heavily trimmed: ~40 % of the current backend and ~30 % of the frontend go away. The agent runtime is **new code** written against a public architectural design. The construction-specific layer rides on top of the agent runtime — clash detection, RFI generation, deliverable approval, site walks become workflows.

**Honest budget:** ~20 engineer-weeks to a pilot-ready product. Solo full-time ≈ 5 months. Two engineers in parallel ≈ 3 months.

---

## 1. Current state — full code scrub

### 1.1 Backend (`server/rapidly/`, ~75k LOC Python)

| Module | LOC | Verdict |
|---|---:|---|
| `admin/` | 13,530 | **Keep** — HTMX admin console; reusable across products |
| `sharing/` | 9,721 | **Trim** — see §1.1.1 |
| `projects/` | 6,637 | **Trim** — see §1.1.2 |
| `models/` | 6,344 | **Keep, prune** — drop the ORM rows for removed domains |
| `identity/` | 5,761 | **Keep all** — auth, oauth2, member, member_session, login_code |
| `analytics/` | 5,654 | **Keep, repurpose** — becomes the agent-run trace store |
| `platform/` | 5,153 | **Keep all** — workspace, member, access_token, user, search |
| `integrations/` | 4,794 | **Keep + extend** — Stripe/GitHub/Google/etc. retained; add ProjectWise/ACC/Aconex |
| `customers/` | 4,231 | **Remove** — customer portal for file sales; not needed |
| `messaging/` | 3,699 | **Keep all** — email, notifications, webhook, email_update |
| `catalog/` | 3,499 | **Trim** — keep `catalog/file`, drop `catalog/share` and `catalog/custom_field` if unused |
| `core/` | 3,196 | **Keep all** — base queries, pagination, types |
| `billing/` | 2,246 | **Keep** — Stripe Connect for usage-based agent billing |
| `worker/` | 1,538 | **Keep** — Dramatiq registry |
| `observability/` | 1,176 | **Keep** — structlog, sentry, logfire, prometheus |
| `errors/` | 303 | **Keep** |
| `middlewares/` | 284 | **Keep** |
| `health/` | 53 | **Keep** |

**Total backend keep:** ~52k LOC. **Remove:** ~16k LOC. **Convert:** ~7k LOC (collab → markup, work_item → coordination).

#### 1.1.1 `sharing/` breakdown

| Submodule | LOC | Verdict |
|---|---:|---|
| `file_sharing/` | 7,492 | **Remove** — P2P file send is out of scope |
| `screen/` | 567 | **Remove** — WebRTC screen share unrelated |
| `watch/` | 517 | **Remove** — watch-together unrelated |
| `call/` | 445 | **Remove** — voice call unrelated |
| `collab/` | 442 | **Keep — rename to `markup/`** — becomes the engineering markup foundation |
| `storefront/` | 257 | **Remove** — public file-sharing storefront |

#### 1.1.2 `projects/` breakdown

22 sub-submodules. Most were built during the Plane-mirror session and are not yet on `main` (they live on the 22 open PRs that should be **closed** — §3). What's actually on `main`:

| On main | LOC | Verdict |
|---|---:|---|
| `work_item/` | 747 | **Keep, rename** — becomes the coordination primitive |
| `project/` | 672 | **Keep, simplify** — projects of work |
| `estimate/`, `module/`, `cycle/`, `page/`, `comment/`, `deploy_board/`, `link/`, `label/`, `state/`, `favorite/`, `activity/` | ~5,250 | **Keep slimmed-down set:** state, label, comment, activity — drop the rest |

The 22 open PRs adding `member/`, `external_link/`, `view/`, `page_version`, `attachment/`, `subscriber/`, `reaction/`, `work_item_type/`, `member_invite/`, `module_extras/`, `user_property/`, `mention/`, `resource_user_property/`, `sticky/`, `recent_visit/`, `vote/`, `intake/`, `analytic_view/`, `deploy_board/` should be **closed without merging** (§3).

### 1.2 Frontend (`clients/apps/web/`, ~70k LOC TS)

| Area | LOC | Verdict |
|---|---:|---|
| `utils/collab` | 37,699 | **Keep** — markup foundation. 140+ files; renderer/provider/rough/tools/shapes/mermaid/persistence/laser/library/command-palette all here |
| `utils/file-sharing` | 5,487 | **Remove** |
| `utils/p2p` | 2,403 | **Trim** — the parts shared with `collab/` (signaling envelope, encryption) stay; file-sharing-specific code goes |
| `utils/watch` + `utils/call` + `utils/screen` | 2,534 | **Remove** |
| `utils/crypto` | 424 | **Keep** — used by markup E2EE |
| `utils/client` + `utils/api` | 158 | **Keep** — OpenAPI client glue |
| `components/Collab` | 4,631 | **Keep, evolve** — becomes `components/Markup/`. Whiteboard subfolder is 3,140 LOC |
| `components/FileSharing` | 3,965 | **Remove** |
| `components/Settings` | 1,990 | **Keep** — workspace settings, OAuth, webhooks |
| `components/Landing` | 1,487 | **Rewrite** — `Landing/file-sharing` (1,059 LOC) goes; new landing for the engineering suite |
| `components/Metrics` | 1,103 | **Keep** — analytics dashboard surfaces |
| `components/Call` | 393 | **Remove** |
| `components/CustomerPortal` | 372 | **Remove** |
| Other components (Auth, Charts, Toast, Modal, Search, FileUpload, Layout, Widgets) | ~5,500 | **Keep** |
| `hooks/file-sharing` | 2,888 | **Remove** |
| `hooks/api` | 1,616 | **Keep** — typed query hooks |
| `hooks/collab` | 523 | **Keep** |
| `hooks/watch` + `hooks/screen` + `hooks/call` | 1,167 | **Remove** |
| `app/(main)/preview/projects` + `app/(main)/dashboard` + `app/(main)/signup` etc. | ~520 | **Keep, restructure** — `/preview/projects` becomes `/coordination`; add `/agents`, `/markup`, `/documents` |

**Total frontend keep:** ~48k LOC. **Remove:** ~22k LOC. The biggest cull is `FileSharing/` + `file-sharing` utils + hooks.

### 1.3 Models layer (`server/rapidly/models/`)

ORM rows to **remove**:

- `file_share_*` (download, payment, report, session)
- `share*` (Share, ShareCustomField, ShareMedia, SharePrice*, ShareVisibility)
- `customer*`, `payment*` (keep `account` if Stripe Connect stays)
- `external_event` if not used by anything else
- `workspace_review` if unused

ORM rows to **keep + simplify**:

- `project`, `project_state`, `project_label`, `work_item`, `work_item_comment`, `work_item_activity`, `work_item_assignee`, `work_item_label`, `work_item_relation`
- Drop the rest of the project_* family (cycle, module, module_work_item, page, estimate, estimate_point, deploy_board, favorite, etc.)

ORM rows to **add** (§5):

- `agent_*` family: workflow, workflow_version, node, run, node_run, dataset, eval_run, integration_credential
- `federated_model`, `model_discipline`, `clash`, `clash_status`
- `markup_layer` extension to existing markup elements
- `deliverable`, `rfi`, `rfi_response`

### 1.4 Infrastructure (`server/docker-compose.yml`, `terraform/`, `.github/workflows/`)

| Resource | State | Verdict |
|---|---|---|
| Postgres (`db`) | Live | **Keep** — main store |
| Redis | Live | **Keep** — Dramatiq broker, channel state |
| MinIO + minio-setup | Live | **Keep** — S3-compatible blob store |
| Tinybird | Live | **Keep** — analytics aggregations; reuse for agent-run aggregates |
| ClamAV | Live | **Keep** — file-upload AV scan |
| Prometheus + Grafana | Live | **Keep** — observability |
| `docker-compose.coturn.yml` | Live | **Remove** — TURN was for P2P file/screen/call |
| Hetzner via Terraform (`terraform/`) | Live | **Keep** — production runs here |
| GitHub Actions (22 workflows) | Live | **Keep + add** — see §10 for the new no-attribution grep gate |

### 1.5 Dependencies already in place that we'd otherwise need to add

These are non-trivial existing dependencies that materially shrink the build cost:

**Backend (`server/pyproject.toml`):**
- `pydantic-ai-slim[openai]` — already imported. We have an LLM client foundation. Add Anthropic + Google extras to it; that's the agent's LLM layer.
- `sentry-sdk[fastapi,sqlalchemy]`, `logfire`, `posthog`, `prometheus-client` — telemetry stack ready for agent traces.
- `clickhouse-connect` — analytics column store, can hold agent-run events.
- `boto3` — S3 already wired. Used for asset storage; will also hold model files.
- `httpx` + `httpx-oauth` + `authlib` + `pyjwt` — OAuth client stack ready for ProjectWise/ACC/Aconex.
- `apscheduler` — already pulled in; could drive scheduled workflow runs.
- `dramatiq[redis,watch]` — task queue ready for workflow execution.

**Frontend (`clients/apps/web/package.json`):**
- `@ai-sdk/anthropic`, `@ai-sdk/google`, `@ai-sdk/mcp`, `@ai-sdk/react`, `@modelcontextprotocol/sdk` — **the entire AI SDK is already a dep**. This is a big head start for the agent-builder UI's LLM bits and for MCP tool integration.
- `yjs` — already a dep. The markup chamber's collaboration foundation.
- `@tanstack/react-query`, `@tanstack/react-table` — fine for the agent traces UI.
- `@stripe/react-stripe-js` — billing UI ready.

**Will need to add:**
- `@xyflow/react` — the React Flow graph editor for the agent builder. Required.
- A web 3D viewer library: **xeokit-sdk** (recommended) or `web-ifc` / `three.js` + IFC.js modules. License decision in §11.
- Server-side IFC tooling: **IfcOpenShell** Python lib for parsing/federation/property queries.

---

## 2. Target state — the suite

**Revised 2026-05-21 (Framing B).** The product pitch leads with the
three surfaces where Rapidly genuinely beats the engineering-tool
incumbents. file_sharing is kept as **transport infrastructure** for
Markup (and for occasional live-handoff use), not as a top-level
product surface. There is no "Files" chamber in the nav. Documents
(durable storage with versions + ACL) is **out of scope** —
engineers will keep using Aconex/SharePoint/BIM360 for their primary
async file workflow; Rapidly does not try to displace that.

```
                  Rapidly Engineering Suite
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
     Markup              Agents             3D Viewer
   (sharing/collab    (new, clean-       (xeokit-sdk,
    renamed → markup) room agent runtime) IFC + GLB)
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                    Coordination (ambient)
                  (work_item, project, state,
                   comment, activity — slim)
                            │
                shared:  identity / platform / billing /
                         messaging / analytics / observability
                         + file_sharing (transport, not surface) +
                         catalog/file (storage primitives, no
                         versioning/ACL product on top)
```

### 2.1 Markup chamber

The existing whiteboard (rich element model, Yjs+WebRTC+E2EE, ~37k LOC of utilities), evolved with:

- **`PdfUnderlayElement`** — a new element type whose painter draws a PDF page beneath the markup layer.
- **`ImageUnderlayElement`** — same for raster scans.
- **`ModelViewportElement`** — embed a 3D model view as an element; markup pins land at world coordinates inside the model.
- **Drawing scale + dimension overlay** — the existing alignment-guides/dimensions overlay extended with engineering units.
- **Linked RFIs and clashes** — element field `linkedEntityRef: { kind: 'rfi'|'clash', id: UUID }` so a markup pin on a plan is queryable as "the markup for clash X."

### 2.2 Agents chamber

A new domain `server/rapidly/agents/` implementing a clean-room rewrite of the public architectural design of a graph-UI agent builder. Submodules:

| Submodule | Responsibility |
|---|---|
| `workflow/` | `Workflow(id, workspace_id, project_id, name, graph_json, version)` + CRUD |
| `node/` | Typed node catalog (see §5.2) + per-node JSON schemas |
| `execution/` | Dramatiq actor that walks a DAG, persists `NodeRun` rows, streams events |
| `dataset/` | Test-case inputs for evals |
| `eval/` | `EvalRun(workflow_version_id, dataset_id, metrics)` |
| `rag/` | Vector store abstraction (Postgres+pgvector v1) — parse/chunk/embed/upsert/query |
| `trace/` | Surface over `analytics/eventstream` for run timeline + per-node IO |
| `credential/` | Encrypted secret store for integration tokens |
| `agent_integration/` | Connectors for HTTP APIs, file systems, BIM tools (§6) |

Frontend: `clients/apps/web/src/app/(main)/agents/` with the `@xyflow/react` editor, node palette, properties panel, run tab, eval tab, deploy tab.

### 2.3 Coordination chamber

A simplified slice of today's `projects/`:

- `project` — projects of work
- `state` — workflow states per project (kept from existing model)
- `label` — labels
- `work_item` — renamed to **task** in user-facing copy; same row
- `comment`, `activity` — kept
- `deliverable` — new entity: a work item tagged as a deliverable with discipline + due date
- `rfi` — new entity: tied to a clash and/or a markup pin
- `approval` — new entity: a state machine row tracking review

Drop everything else from current `projects/`.

### 2.4 Documents — out of scope

Originally listed as a chamber. Cut after the 2026-05-21 framing
decision. Rapidly doesn't try to be an async document store with
versioning + ACL — engineers will keep their daily document workflow
in Aconex/SharePoint/BIM360. `catalog/file` stays as a storage
primitive (it backs file_sharing transfers and any Markup
attachments) but there is no product surface called "Documents".

### 2.5 What's removed entirely

- `sharing/screen`, `sharing/watch`, `sharing/call` (consumer-y chambers; not engineering use cases)
- `sharing/storefront` (Polar-inherited; never used)
- `customers/` and `customers/customer_portal/` (B2C surface; engineering suite is workspace-internal)
- Frontend `components/Screen`, `components/Watch`, `components/Call`, `components/Storefront`, `components/CustomerPortal`, `utils/screen`, `utils/watch`, `utils/call`, `hooks/screen`, `hooks/watch`, `hooks/call`, `clients/packages/customer-portal/`

### 2.6 What's kept (Framing B)

- **`sharing/file_sharing/`** — entire P2P chamber, COTURN, signaling, E2EE. No top-level nav entry; powers the Markup chamber's transport and remains available as a "send live" handoff for the niche where E2EE + no-server-bandwidth genuinely beats the incumbents.
- **`sharing/collab/` → renamed to `sharing/markup/`** — the markup chamber.
- **`catalog/share/`** — dashboard entry point to file_sharing. Kept because file_sharing is kept.
- **`admin/file_sharing/`** — admin UI for the kept chamber.
- **`messaging/webhook` file-share handlers** — kept (events for the kept chamber).
- **`docker-compose.coturn.yml` + COTURN** — kept (Markup uses it, file_sharing uses it).

---

## 3. The 22 open PRs from the Plane-mirror session

PRs **#698 through #722** (members backend/hooks/UI, external links, saved views, page versioning, notifications, attachments, subscribers, reactions, work-item types, member invites, module roster, project user properties, mentions, cycle/module user properties, sticky, recent visits, votes, intake, analytic view, deploy board) are **wrong scope** for the new direction.

**Action: close all 22 without merging.** Branches remain in the repo for archeology. Update `MEMORY.md` with a single line noting the abandonment so future sessions don't try to resurrect them.

---

## 4. Gap analysis — what we have vs. what we need

| Need | What we already have | Gap |
|---|---|---|
| LLM client layer | `pydantic-ai-slim[openai]` on backend; full Vercel `@ai-sdk/*` on frontend | Add Anthropic + Google extras to backend; wire `@ai-sdk/anthropic` server-side via a thin adapter |
| MCP tool support | `@modelcontextprotocol/sdk` (frontend) | Add `mcp` Python lib server-side |
| Real-time collab CRDT | `yjs` + custom E2EE provider | Reuse as-is for the agent builder's graph (live multi-edit on a workflow) |
| Graph editor UI | Nothing — no React Flow yet | **Add `@xyflow/react`** |
| Workflow runtime | Nothing | **Build clean-room** — see §5 |
| Vector store | None — no pgvector | **Add `pgvector` Postgres extension** + Python adapter |
| 3D model viewer | None | **Add xeokit-sdk** (commercial OR LGPL-compatible alternative) — see §11 |
| IFC parsing server-side | None | **Add IfcOpenShell** |
| File storage + AV scan | MinIO + ClamAV already wired | Reuse |
| Auth + scopes + workspace tokens | Already mature | Reuse — much stronger than typical agent builders' auth |
| Task queue | Dramatiq + Redis | Reuse for workflow execution |
| Event streaming | `analytics/eventstream` SSE | Reuse for agent-run trace streaming |
| Notifications + email | Full stack already wired | Reuse for workflow alerts + RFI notifications |
| Billing | Stripe Connect | Reuse — add usage-based metering on workflow runs |
| Observability | structlog/Sentry/Logfire/Prometheus | Reuse |
| Hetzner deploy + Terraform | Live | Reuse — adjust container sizes for IFC parsing memory needs |

**Net:** the gap is **the agent runtime + a 3D viewer + IFC parsing + a few new entities for construction**. Everything else is already in place or only needs trimming.

---

## 5. The agent runtime — clean-room design

The architecture below is *Rapidly's design*. It's informed by reading public design documentation of a similar open-source product, but no code is copied. Implementation is in our `actions.py` + `queries.py` + `types.py` + `permissions.py` per-module convention.

### 5.1 Domain model

```
Workflow
  id, workspace_id, project_id (nullable), name, description
  current_version_id → WorkflowVersion
  archived_at

WorkflowVersion
  id, workflow_id, version_number
  graph_json (JSONB): { nodes: [...], edges: [...] }
  created_by_id, created_at

Run (= WorkflowRun)
  id, workflow_version_id, triggered_by_id (User|Webhook|Schedule)
  status enum: pending, running, succeeded, failed, cancelled, awaiting_human
  started_at, completed_at, error_message
  input_data (JSONB)
  output_data (JSONB)

NodeRun
  id, run_id, node_id (from graph_json), node_type
  status enum: pending, running, succeeded, failed, skipped, awaiting_human
  started_at, completed_at
  input_data, output_data, error_message
  trace_events (relation to analytics events)

Dataset
  id, workspace_id, project_id, name
  schema_json (JSONB)

DatasetRow
  id, dataset_id, row_index, data (JSONB), expected_output (JSONB)

EvalRun
  id, workflow_version_id, dataset_id
  metric_results (JSONB): { 'accuracy': 0.87, 'avg_latency_ms': 1240, ... }
  started_at, completed_at

IntegrationCredential
  id, workspace_id, kind enum, name
  encrypted_payload (BYTEA) — fernet-encrypted via existing crypto stack
  created_by_id
```

### 5.2 Node catalog v1

| Node | Inputs | Outputs | Notes |
|---|---|---|---|
| **LLM** | prompt, model, temperature, structured_schema (optional) | text or structured JSON | Routes via `pydantic-ai-slim`; provider = Anthropic / OpenAI / Google / Ollama |
| **HTTP** | url, method, headers, body | response body, status | Calls out to arbitrary HTTP APIs |
| **Code** | python source, args | return value | Sandboxed Python via gVisor / subprocess (security-sensitive — see §9) |
| **File read** | document_id or path | bytes / text | Reads from MinIO via `catalog/file` (later `documents`) |
| **File write** | bytes, name | document_id | Writes to MinIO, registers a Document version |
| **Branch** | condition expression | one of N outputs | Conditional dispatch |
| **Loop** | iterable, body subgraph | aggregated output | Bounded iterations; memory of prior runs |
| **Human-in-loop** | prompt to human, schema | human response | Pauses the run, posts a notification, resumes on response |
| **Sub-workflow** | input | output | Invokes another `Workflow` by id |
| **RAG search** | query, vector_collection | top-k results | Postgres pgvector lookup |
| **Structured output** | unstructured input, target schema | structured output | LLM-backed; first-class because the UI editor for the schema is a dedicated tool |
| **Construction nodes** (see §6) | … | … | Clash detection, RFI draft, deliverable check, model parse, etc. |

### 5.3 Execution semantics

- `Run.start` schedules a Dramatiq actor.
- The actor performs a topological walk; nodes with no unresolved inputs are queued.
- Parallel branches execute in separate Dramatiq actors that report into the same `Run` row.
- Each node call writes a `NodeRun` row at start and updates on completion. Trace events flow into `analytics/eventstream` (SSE consumers see them live in the UI).
- Human-in-loop nodes set `Run.status = awaiting_human` and emit a notification (existing notification stack). The run resumes on the resolution endpoint.
- Cancellation: a `Run.cancel` endpoint marks the run cancelled and signals the actor via a Redis pub/sub key.
- Retries: per-node retry policy. Failed nodes can be re-run from a checkpoint by spawning a new `Run` with `parent_run_id` set.

### 5.4 Frontend

Single-page editor at `/agents/[workflowId]`:

- Left panel: node palette grouped by category (Inputs, Logic, AI, Integrations, Construction).
- Center: React Flow canvas (`@xyflow/react`) showing the DAG. Drag nodes from the palette; drag edges between handles.
- Right panel: properties for the selected node; for LLM nodes this includes prompt editor (Tiptap/markdown), model selector, structured-output schema editor.
- Top tabs: **Editor** | **Runs** | **Evals** | **Deploy**.
- Live multi-edit: the graph_json lives in a Yjs document so two engineers can co-edit a workflow with the same E2EE envelope as Markup.

### 5.5 Existing Rapidly affordances we reuse

- Workflow JSON is stored in Postgres but **mirrored to Yjs** for live editing. The encryption envelope from the markup provider applies untouched.
- `analytics/eventstream` SSE — the trace tab subscribes to a stream filtered by `run_id`.
- `messaging/notifications` — human-in-loop notifications, run-failure alerts, deliverable approvals.
- `platform/workspace_access_token` — to invoke a published workflow as an API.
- `billing/payment` — usage-based metering on `Run.completed_at` events.

---

## 6. The construction layer — agentic reimagining

This sits on top of the agent runtime. It's the differentiator. Our design reference is a category of construction-deliverables / coordination products that have historically lived as desktop plugins inside a specific 3D federation tool; our take inverts that — the platform is cloud-first and agents are the primary actors, with humans intervening at named gates rather than driving the tool. We are explicitly *not* cloning any one of those products' UIs or feature lists.

### 6.1 Construction-specific entities

| Entity | Definition |
|---|---|
| `FederatedModel` | A combined 3D model built server-side via IfcOpenShell from N discipline IFC files (architectural, structural, MEP, …) |
| `ModelDiscipline` | Per-discipline IFC; references one or more uploaded IFC documents |
| `Clash` | Geometric or rule-based conflict between two model elements; emitted by the clash-detection node |
| `ClashStatus` | Triage state: new, assigned, in-progress, resolved, won't-fix |
| `RFI` | Request for information; ties to clashes and/or markup pins |
| `Deliverable` | A work item flagged as a contractual deliverable, with discipline + due date + approval state |
| `Approval` | Generic approval row tied to deliverable or RFI; ordered approvers, current step |

### 6.2 Construction node types (added to §5.2 catalog)

- **Federate model** — input: discipline IFC files. Output: `FederatedModel`. Runs IfcOpenShell in a Dramatiq worker.
- **Detect clashes** — input: `FederatedModel`. Output: list of `Clash` rows. Wraps a clash-detection routine (hard clash + clearance clash).
- **Route clash** — input: `Clash`. Output: assigned discipline lead. Uses workspace roster + element properties.
- **Generate RFI draft** — input: `Clash` + markup pin. Output: `RFI` draft text. LLM node, structured-output enabled, prompt template versioned.
- **Validate deliverable** — input: `Deliverable` + checklist schema. Output: pass/fail + issues. Mix of static rules + LLM review.
- **Notify discipline lead** — input: User + payload. Output: notification record. Wraps existing notification stack.
- **Extract model properties** — input: IFC element id. Output: property dict. IfcOpenShell read.
- **Site walk capture** — input: photo + voice transcript. Output: tagged work items + markup pin coordinates. Sits in a workflow triggered by mobile uploads.

### 6.3 Canonical workflows

These ship as workspace-importable starter templates:

1. **Daily clash sweep** — federate → detect → route → generate RFI drafts → human approval per discipline lead → notify.
2. **Deliverable submission** — upload check → validate → discipline approvals → publish → notify client.
3. **Site walk → punch list** — photos in → LLM tags → create work items → mark on plan via markup.
4. **Drawing change log** — new revision uploaded → diff vs prior → flag impacted RFIs/clashes → notify affected leads.

### 6.4 Integrations

| Integration | What it does | Status |
|---|---|---|
| Bentley ProjectWise | Document control, model fetch | New — REST API via existing httpx-oauth |
| Autodesk ACC (Construction Cloud) | Sheets, RFIs, model store | New |
| Aconex (Oracle) | Document control, transmittals | New |
| **MCP servers** | Generic LLM-tool extension | **Already supported** — `@modelcontextprotocol/sdk` on frontend; add `mcp` python package server-side |
| Slack, Teams, Email | Notification outbound | Existing webhook + email stack |

---

## 7. Markup chamber — engineering markup evolution

The existing whiteboard becomes the markup chamber with these additions:

### 7.1 New element types

```ts
interface PdfUnderlayElement extends BaseElement {
  type: 'pdf-underlay'
  documentId: string       // points at a Document version
  page: number             // 1-indexed
  /** Scale factor: world units per drawing unit. */
  scale: number
}

interface ImageUnderlayElement extends BaseElement {
  type: 'image-underlay'
  assetHash: string        // existing collab asset store
  /** Optional registration so the markup overlay can derive world coords. */
  worldOrigin?: { x: number; y: number }
  worldScale?: number
}

interface ModelViewportElement extends BaseElement {
  type: 'model-viewport'
  federatedModelId: string
  /** Saved camera + section state. */
  cameraJson: object
  sectionPlanes: object[]
  /** Element-local rect within the canvas. */
}

interface ClashPinElement extends BaseElement {
  type: 'clash-pin'
  clashId: string
  /** 3D world coord of the pin in the federated model. */
  worldPosition: [number, number, number]
}

interface RfiPinElement extends BaseElement {
  type: 'rfi-pin'
  rfiId: string
}
```

### 7.2 Drawing-specific overlays

- **Dimension overlay** — already exists in `utils/collab/dimensions-overlay.ts`; extend to engineering units (mm/m/in/ft) with a per-board setting.
- **Scale calibration** — a one-click tool: click two points, enter real-world distance, scale is calibrated. Stored on the board.
- **Sheet borders + title block** — recognised regions on PDF underlays, used to lock the markup to the drawing's coordinate system.

### 7.3 The viewer

A `xeokit-sdk`-based viewer mounted inside `ModelViewportElement`. The viewer is loaded lazily on element creation. Federated-model bytes are stored encrypted in MinIO; the viewer fetches via a signed URL and decrypts client-side.

The markup canvas paints on top of the viewer DOM layer, with mouse events forwarded to the viewer when the active tool is "pan/orbit" and to the canvas otherwise.

---

## 8. Phased plan

### Milestone M0 — Close-out and CI gate (0.5 week)

- Close PRs #698–#722 (one-line `gh pr close` each).
- Add CI gate: pre-commit hook + GitHub Action that fails the build if the upstream agent platform's name appears anywhere in the repo outside the single memory file that documents the rule.
- Update `MEMORY.md` to mark the Plane mirror abandoned and reference this plan.

### Milestone M1 — Demolition (1.5 weeks)

- One PR per major surface removal:
  - `feat/demo-1-remove-file-sharing` — `sharing/file_sharing/` backend + frontend + COTURN.
  - `feat/demo-2-remove-media-chambers` — `sharing/screen/`, `sharing/watch/`, `sharing/call/`.
  - `feat/demo-3-remove-storefront` — `sharing/storefront/` + landing pages.
  - `feat/demo-4-remove-customers` — `customers/` + `customer_portal` everywhere.
  - `feat/demo-5-remove-catalog-share` — `catalog/share/` + ORM rows + frontend FileSharing components.
  - `feat/demo-6-trim-projects` — keep `project`, `state`, `label`, `work_item`, `comment`, `activity`; drop the rest.
- Run full test suite after each removal. Type-check and lint must stay green.
- Rename `sharing/collab/` → `sharing/markup/` (backend) and `components/Collab/` → `components/Markup/` (frontend). Update routes from `/collab/` to `/markup/`.

### Milestone M2 — Engineering primitives (2 weeks)

- Add `Document` (renamed `catalog/file` with version history + ACL).
- Add markup element types: `PdfUnderlayElement`, `ImageUnderlayElement`.
- PDF rendering: `pdfjs-dist` in the markup canvas painter.
- Scale calibration tool + engineering-units dimension overlay.

### Milestone M3 — Self-hosted 3D viewer (3 weeks)

- Decide on viewer license (§11).
- IfcOpenShell Dramatiq worker for parsing + federation. Memory-bound; tune container size.
- New ORM rows: `FederatedModel`, `ModelDiscipline`.
- Frontend `ModelViewportElement` with lazy-loaded viewer.
- Pin tools (Clash pin / RFI pin) wired to markup.

### Milestone M4 — Agent runtime backend (4 weeks)

- New domain `server/rapidly/agents/` with submodules: `workflow`, `node`, `execution`, `dataset`, `eval`, `rag`, `trace`, `credential`.
- Node catalog v1 (LLM, HTTP, code, branch, loop, RAG search, structured output, human-in-loop, sub-workflow, file read/write).
- Dramatiq actor for run execution. Trace events flow into `analytics/eventstream`.
- pgvector extension + Postgres setup.
- Workflow CRUD endpoints; Yjs sidecar for collaborative editing.

### Milestone M5 — Agent runtime UI (3 weeks)

- Add `@xyflow/react`. Build node-graph editor under `/agents/`.
- Node palette grouped by category.
- Properties panel — generic schema-driven form (one component per node-type config).
- Run tab — timeline view of node-runs streamed from SSE.
- Eval tab — dataset upload, results grid.
- Deploy tab — token-secured webhook endpoint to invoke a workflow.

### Milestone M6 — Construction node types + workflows (3 weeks)

- Clash detection node (IfcOpenShell-backed).
- Clash routing rules.
- RFI draft LLM node.
- Deliverable validation node.
- Site walk capture workflow.
- Starter workflow templates importable into any workspace.
- New ORM rows: `Clash`, `ClashStatus`, `RFI`, `Deliverable`, `Approval`.

### Milestone M7 — Construction integrations (3 weeks)

- ProjectWise OAuth + REST adapter.
- ACC OAuth + REST adapter.
- Aconex OAuth + REST adapter.
- Server-side `mcp` python lib for MCP tool calls.

### Milestone M8 — Mobile + polish (2 weeks)

- Tablet PWA for the markup chamber on construction-site iPad use.
- Photo + voice capture flow that hits the site-walk workflow.
- Perf pass on federated models > 1 GB.

### Milestone M9 — Pilot (open-ended)

- One design-partner construction project.
- Iterate on workflow templates based on real use.

**Total:** ~20 engineer-weeks before pilot. Calendar-time:

| Team | Time to pilot |
|---|---|
| 1 engineer full-time | ~5 months |
| 2 engineers parallel | ~3 months |
| 3 engineers parallel | ~2.5 months |

---

## 9. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Sandbox-escape from the **Code** node | Med | Critical | gVisor or `subprocess.run` with seccomp; explicit allowlist of importable modules; no network access from the sandbox |
| IFC parsing OOM on large models | High | Medium | Per-discipline workers with explicit memory limits; degrade to "section-by-section" parsing for files > 500 MB |
| Viewer license cost surprise | Med | Low | xeokit's pricing is published; if a blocker, fall back to IFC.js + three.js |
| LLM prompt-injection leaking workspace data | Med | High | Per-workflow allowlist of which Documents/integrations a workflow may touch; prompt-injection regex sniffing on tool-call outputs |
| Workflow runtime cost explosion | Med | Medium | Hard per-run timeout (default 5 min, configurable per workflow); per-workspace concurrent-run cap; usage-based billing surfaces cost |
| Existing 22 open PRs cause review noise | Low | Low | Close all in M0; branches remain accessible if anything's ever needed |
| Markup element model conflicts with new types | Low | Low | The element model is already a discriminated union — adding 5 new variants is well-typed and well-tested |
| Yjs doc size for big workflows | Med | Low | The existing chunked-sync + compression in the markup provider handles the 64 KB envelope cap; reuse |
| Construction integration auth complexity | High | Medium | Each vendor has its own OAuth quirks; budget extra weeks in M7 |

---

## 10. Operating rules

### 10.1 No upstream attribution

The agent runtime is informed by reading a public open-source design doc. **No reference to that upstream may appear anywhere in our repo** — code, comments, docstrings, commit messages, branch names, PR titles, design docs, UI strings, or memory entries. The single rule-doc memory file (outside the repo, under `~/.claude/projects/.../memory/`) is the only place the upstream name exists; everywhere else uses neutral language ("the agent runtime", "the workflow builder").

Enforced by:

- **Pre-commit hook**: `git diff --staged | grep -iE '<the-upstream-name>' && exit 1` (case-insensitive). The literal pattern lives only in the hook script + the rule-doc memory file.
- **GitHub Action**: same grep over the diff of every PR. Hard fail.
- **PR review checklist** item: "No upstream attribution in this diff."

The exception is the single rule-doc memory file under `~/.claude/projects/.../memory/`; the gate must allow that path explicitly.

### 10.2 Clean-room policy

Per the existing `feedback_clean_room_policy.md`, the agent runtime is a **clean-room rewrite**, not a vendor. We read the public README + docs of the upstream, build a spec for Rapidly, and implement against the spec — never reading the upstream source while writing ours.

### 10.3 Definition of Done

Every PR in M1–M9 must:

- Stamp the per-PR DoD checklist from `feedback_pr_quality_checklist.md`.
- Pass the full `verify.sh` (backend + frontend lint/types/tests + Playwright e2e) locally before pushing.
- Cite the references read for any non-trivial subsystem (public spec, not source).

### 10.4 No AI features in unrelated chambers

The `feedback_no_ai.md` rule from the Collab chamber stays. AI features are scoped to the **Agents** chamber and to the construction nodes that explicitly call LLMs. Markup, Coordination, and Documents stay AI-free at the UI level — they can be inputs/outputs of agent workflows but don't sprout their own auto-summarise buttons.

---

## 11. Open decisions

Resolved during plan drafting (2026-05-21 / 24):

| # | Decision | Resolution | Resolved in |
|---|---|---|---|
| 1 | xeokit-sdk commercial license vs IFC.js + three.js | **xeokit-sdk MIT** (community edition); per the pivot memory's "OSS-licensed" mandate, the commercial license is skipped | M3_EXECUTION.md |
| 2 | LLM provider priority for v1 | **Anthropic primary, OpenAI secondary, Google + Ollama via pydantic-ai** | M4_EXECUTION.md §4.4 |
| 5 | Landing-page direction | **Engineering-suite landing**; revolver framing superseded by Framing B | this doc §2 + M1.0 |
| 6 | Mobile scope | **Tablet PWA, phone read-only** | M8_EXECUTION.md |
| 7 | Code-sandbox tech | **subprocess+seccomp+rlimit** for v1; gVisor deferred to M9 | M4_EXECUTION.md §4.5 |
| 8 | MCP server hosting | **Allowlist** (workspace-admin-curated); stdio gated behind separate flag + sandbox | M7_EXECUTION.md §7.5 |

Still open (blocks M5 / M6 / M9 respectively):

| # | Decision | Blocks |
|---|---|---|
| 3 | Pilot construction partner | M6 / M9 |
| 4 | Pricing model (usage-based, seat-based, both) | M5 deploy tab metering |

Additional decision made during M1 drafting (not in the original list):

| # | Decision | Resolution | Resolved in |
|---|---|---|---|
| 9 | What's "Files" in the engineering-suite UI? | **Framing B:** file_sharing kept in code as transport infrastructure for Markup + niche live-handoff. No "Files" chamber in the nav. Suite leads with Markup + Agents + 3D Viewer. | this doc §2.6 + M1.0 |
| 10 | Async durable storage / Documents chamber? | **Out of scope.** Engineers keep their async document workflow in Aconex/SharePoint/BIM360. `catalog/file` stays as a storage primitive (transport for file_sharing + markup asset store); no Documents product surface. | this doc §2.4 |

---

## 12. What this document replaces

- The Plane integration audit work from the prior session (22 open PRs) is **closed**.
- The existing `COLLAB_WHITEBOARD_PLAN.md` is **kept** — its work is largely shipped and its phases ride into the Markup chamber. This plan supersedes its forward-looking sections.
- Memory entries to update at M0:
  - `MEMORY.md` — add a top-of-file note pointing at this plan; remove or annotate the Plane mirror references.
  - `project_projects_domain.md` — annotate "abandoned; superseded by Engineering Suite Plan."
  - `project_platform_direction.md` — annotate "revolver/6-chamber direction superseded; new direction is the Engineering Suite."

---

## 13. Next action

**M0 was executed on 2026-05-21.** Status:
- All `feat/projects-*` PRs closed (59 total — the 22 from this session plus 37 older Plane-mirror PRs from earlier sessions).
- M0 PR #723 opened — adds the no-attribution gate workflow + this plan file + `M0_EXECUTION.md` to main.
- Awaiting two user actions to fully complete M0: (1) set the `BLOCKED_PATTERN` Actions secret, (2) merge #723, (3) add `scan` to required-status-checks.

**M1–M8 are fully drafted** (one `M<N>_EXECUTION.md` per milestone, all leak-free against the gate). 54 PRs across ~17 engineer-weeks of work:

| Milestone | Plan | PRs | ~Weeks |
|---|---|---|---|
| M1 — Demolition | M1_EXECUTION.md | 6 | 1.5 |
| M2 — Markup engineering primitives | M2_EXECUTION.md | 4 | 1 |
| M3 — 3D viewer + IFC ingestion | M3_EXECUTION.md | 6 | 3 |
| M4 — Agent runtime backend | M4_EXECUTION.md | 8 | 4 |
| M5 — Agent runtime UI | M5_EXECUTION.md | 7 | 3 |
| M6 — Construction layer | M6_EXECUTION.md | 6 | 3 |
| M7 — Vendor integrations | M7_EXECUTION.md | 5 | 3 |
| M8 — Mobile + polish | M8_EXECUTION.md | 5 | 2 |

**Sequencing constraints:**
- M1 must finish before M2 (rename + demolition stable before primitives on top)
- M3 can start after M1 (independent of M2)
- M4 can start after M1 (independent of M2 + M3)
- M5 must wait for M4.1 at minimum
- M6 must wait for M3 + M4 (uses both)
- M7 must wait for M4.7 (IntegrationCredential) + M6 (construction nodes consume vendor data)
- M8 must wait for everything (polish pass touches every chamber)

**M9 — Pilot** is open-ended; first artifact is an `M9_RUNBOOK.md` written when a pilot partner is named (open decision §11/3).

---

*End of plan. Revise this file in place rather than spawning a v2 in a new file.*

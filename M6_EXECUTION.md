# M6 — Construction nodes + canonical workflows

Executable plan for milestone M6 of `RAPIDLY_ENGINEERING_SUITE_PLAN.md`.
M6 turns the generic Agents chamber into something a coordinator,
discipline lead, or design manager would actually pay for: real
construction entities (Clash, Rfi, Approval, Deliverable,
Discipline), construction-specific nodes that run on federated IFC
models, and four canonical workflows shipped as workspace-importable
templates.

**Read M3 + M4 + M5 first.** M6 binds against:
- M3's `FederatedModel` + IfcOpenShell worker pattern.
- M4's agent runtime + node registry.
- M5's UI palette (the Construction category is the empty slot it left).
- M3.6's free-form pin labels (M6.6 tightens these into real entity refs).

## Scope (6 PRs, ~3 weeks)

| # | Branch | What lands |
|---|---|---|
| 6.1 | `feat/coord-entities` | Coordination chamber: `Discipline` / `Clash` / `Rfi` / `Deliverable` / `Approval` ORM + CRUD + UI tabs on the project page |
| 6.2 | `feat/construction-node-federate` | "Federate models" node: combine N `FederatedModel` rows into a federation view; produces a `Federation` row the clash node consumes |
| 6.3 | `feat/construction-node-clash` | "Detect clashes" node: subprocess IfcOpenShell clash detection; writes `Clash` rows tagged to the run |
| 6.4 | `feat/construction-nodes-rfi-notify-extract` | "Generate RFI draft" (LLM-backed) + "Notify discipline lead" + "Extract model properties" (IFC element id → prop dict) |
| 6.5 | `feat/construction-nodes-sitewalk-deliverable` | "Site walk capture" (photo + transcript → work items + markup pins) + "Check deliverable" |
| 6.6 | `feat/construction-canonical-workflows` | Four starter workflows as JSON templates + import flow + tighten M3.6 pin labels to real entity refs |

Per-PR DoD in §6.

## Conventions

- Backend module convention is mandatory (`server/CLAUDE.md`).
- M6 adds to two domains: `server/rapidly/projects/` (the Coordination entities) and `server/rapidly/agents/nodes/` (the construction nodes).
- All M6 PRs run the no-attribution `scan` job — non-negotiable, same as M4.
- Construction nodes that wrap IfcOpenShell follow M3.1's subprocess pattern (memory isolation + OOM-survival).
- Pre-push: backend `uv run task lint && lint_types && test_fast && openapi_export`; frontend `pnpm typecheck && pnpm lint && pnpm test`.

---

## 6.1 — Coordination chamber entities

Branch: `feat/coord-entities`

### Goal

Five new ORM rows under `projects/` (the kept-slim domain after M1.5):
`Discipline`, `Clash`, `Rfi`, `Deliverable`, `Approval`. Each gets a
submodule with the full backend convention + a UI tab on the project
detail page.

### Domain

```
server/rapidly/projects/
├── discipline/        # arch, struct, MEP, civil, ... — workspace-customisable
├── clash/             # clash between two model elements; owns a 3D world position
├── rfi/               # Request for Information; tied to a clash and/or a markup pin
├── deliverable/       # a work item tagged as a deliverable with discipline + due date
└── approval/          # state-machine row tracking review on a deliverable / RFI / page version
```

Each submodule: `api.py / actions.py / queries.py / types.py / permissions.py / ordering.py`. No workers for 6.1; clash detection lands in 6.3.

### ORM rows

```python
# models/discipline.py
class Discipline(BaseEntity):
    __tablename__ = "disciplines"
    workspace_id: Mapped[UUID]
    code: Mapped[str] = mapped_column(String(8))     # 'A', 'S', 'M', 'E', 'C', ...
    name: Mapped[str] = mapped_column(String(64))     # 'Architecture'
    color: Mapped[str] = mapped_column(String(7))     # '#3b82f6'
    __table_args__ = (UniqueConstraint("workspace_id", "code"),)

# models/clash.py
class Clash(BaseEntity, SoftDeleteMixin):
    __tablename__ = "clashes"
    project_id, federation_id (nullable; or use model_id + element_a + element_b directly)
    discipline_a_id, discipline_b_id  # FK to Discipline
    element_a_global_id: Mapped[str] = mapped_column(String(22))  # IFC GUID
    element_b_global_id: Mapped[str] = mapped_column(String(22))
    world_position: Mapped[list[float]] = mapped_column(JSONB)    # [x, y, z]
    severity: Mapped[ClashSeverity]  # 'hard', 'clearance', 'duplicate'
    status: Mapped[ClashStatus]      # 'open', 'in_review', 'resolved', 'ignored'
    distance_mm: Mapped[float | None]  # for clearance clashes
    detected_in_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="set null"))
    resolved_by_id, resolved_at, resolution_note

# models/rfi.py
class Rfi(BaseEntity, SoftDeleteMixin):
    __tablename__ = "rfis"
    project_id, number  # auto-incrementing per project; printed on PDFs
    title, body
    discipline_id (FK)
    clash_id (FK, nullable)               # source clash if the RFI was generated from one
    markup_element_id (str, nullable)      # markup pin id from elements.ts
    status: Mapped[RfiStatus]              # 'open', 'answered', 'closed'
    raised_by_id, raised_at
    answer_body (Text, nullable), answered_by_id, answered_at
    due_date (Date, nullable)
    __table_args__ = (UniqueConstraint("project_id", "number"),)

# models/deliverable.py
class Deliverable(BaseEntity, SoftDeleteMixin):
    __tablename__ = "deliverables"
    project_id, work_item_id (FK to projects.work_item)
    discipline_id (FK)
    spec_json: Mapped[dict] = mapped_column(JSONB)   # spec checks: required scale, units, sheet count, naming convention
    due_date (Date)
    status: Mapped[DeliverableStatus]                # 'planned', 'in_progress', 'submitted', 'approved', 'rejected'
    submitted_document_id (FK to catalog/file, nullable)
    submitted_at

# models/approval.py
class Approval(BaseEntity):
    __tablename__ = "approvals"
    subject_kind: Mapped[ApprovalSubjectKind]   # 'deliverable', 'rfi_answer', 'page_version'
    subject_id (UUID; polymorphic, no FK)
    approver_id (FK to users)
    decision: Mapped[ApprovalDecision | None]    # 'approve', 'reject', 'request_changes'
    decided_at, note
```

### Routes

Standard CRUD per submodule. Plus:

```
POST   /api/clashes/{id}/resolve              status='resolved' + note
POST   /api/clashes/{id}/ignore               status='ignored' + note
POST   /api/rfis/{id}/answer                  answer_body + answered_by + answered_at
POST   /api/deliverables/{id}/submit          submitted_document_id + status='submitted'
POST   /api/approvals/{id}/decide             decision + note
```

### Permissions

- `Discipline`: workspace-admin to create; workspace-member to read.
- `Clash`, `Rfi`, `Deliverable`: project-member to read, project-admin to create/resolve (in line with `projects/deploy_board/actions.py:_ensure_admin` pattern).
- `Approval`: only the named `approver_id` can decide.

### Migration

```bash
cd server
uv run alembic revision -m "coord chamber: discipline, clash, rfi, deliverable, approval tables"
```

Migration order: `disciplines` first; then `clashes`, `rfis`, `deliverables` (FKs to disciplines + work_item); then `approvals`.

Seed: insert 5 default disciplines (Architecture, Structure, Mechanical, Electrical, Plumbing) per workspace at workspace creation. Migration backfills existing workspaces.

### Frontend

Project detail page (`/dashboard/[workspace]/projects/[projectId]/`)
gets three new tabs: **Clashes**, **RFIs**, **Deliverables**. Each is
a paginated list with status filters and a quick-action menu
(resolve, ignore, answer, submit).

A workspace-level page `/dashboard/[workspace]/disciplines/` for
managing disciplines. Workspace-admin only.

### Tests

- ORM round-trip for each entity.
- Per-action role gating (resolve a clash as a non-admin → 403).
- RFI number auto-increments per project (concurrent creates: no collisions, contiguous numbering).
- Approval decided-by enforcement.

### Verify

```bash
cd server
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
uv run task test_fast && uv run task openapi_export
cd ../clients/packages/client && pnpm generate && cd ../../apps/web && pnpm typecheck
```

Manual: create a project, add disciplines, create a clash via the
new tab, resolve it. Create an RFI tied to the clash. Create a
deliverable tied to a work item.

---

## 6.2 — "Federate models" node

Branch: `feat/construction-node-federate`

### Goal

A node that takes N `FederatedModel` ids as input and produces a
`Federation` row representing the union. The Federation is the input
shape for the clash node (6.3).

Why a separate node + entity: federations are reused across runs.
The daily clash sweep can be configured once with the federation
spec and re-execute against the latest model versions.

### Backend

```
server/rapidly/viewer/federation/
├── api.py / actions.py / queries.py / types.py / permissions.py / workers.py
```

```python
# models/federation.py
class Federation(BaseEntity, SoftDeleteMixin):
    __tablename__ = "federations"
    project_id
    name
    member_model_ids: Mapped[list[UUID]] = mapped_column(JSONB)   # [FederatedModel.id, ...]
    /** Cached at federate time. */
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    /** Combined XKT (output of the worker), or null while pending. */
    xkt_file_id: Mapped[UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    status: Mapped[FederationStatus]   # 'pending', 'building', 'ready', 'failed'
```

### Worker

Combine multiple XKTs into a single XKT for viewing + a single IFC
graph for clash detection (6.3 uses this). xeokit-sdk supports
loading multiple XKTs in the same viewer scene; "federation" at the
worker level here is for *clash detection*, which needs all elements
in one geometry graph.

```python
# viewer/federation/workers.py
@actor(actor_name="viewer.build_federation", priority=TaskPriority.LOW, max_retries=2)
async def build_federation(federation_id: UUID) -> None:
    # 1) Fetch source files for each member model.
    # 2) Subprocess: IfcConvert + xeokit's combine tool to produce a single XKT.
    # 3) Compute combined bbox.
    # 4) Upload combined XKT to S3.
    # 5) Update Federation row.
```

### Node

`agents/nodes/federate_models.py`:

```python
async def execute(self, ctx, input_data, node_config):
    # node_config has "federation_id" (re-use existing) or
    # "model_ids" + "federation_name" (create new on first call, reuse on subsequent).
    federation = await get_or_create(ctx.session, ctx.workspace_id, node_config)
    if federation.status != FederationStatus.ready:
        # block until ready or fail-fast after a timeout
        ...
    return {"federation_id": str(federation.id), "model_count": len(federation.member_model_ids)}
```

### Tests

- Federation worker happy path on 2 small IFCs.
- Re-running a federation when source models change → produces a new XKT.
- Worker OOM-survival (artificial memory limit; ensure the worker reports failed, doesn't take down API).

### Verify

Manual: upload 2 federated models (arch + struct sample IFCs), wire a workflow with Trigger → Federate (arch + struct) → End, run, confirm Federation row reaches `ready` within ~30 s.

---

## 6.3 — "Detect clashes" node

Branch: `feat/construction-node-clash`

### Goal

Takes a `federation_id`, runs clash detection inside IfcOpenShell,
writes `Clash` rows tagged with the originating `Run.id` and
returns the clash list + counts.

### Clash detection in IfcOpenShell

IfcOpenShell ships a `clash` tool that performs hard and clearance
clashes between two sets of elements. Algorithm shape:

```
ifcclash --hard --tolerance 0.001 \
  --group_a "IfcWall|IfcSlab|IfcBeam|IfcColumn" \
  --group_b "IfcDuctSegment|IfcPipeSegment|IfcCableSegment" \
  --output clashes.json \
  federation.ifc
```

Subprocess pattern same as 6.2 (and M3.1): the worker shells out,
parses the JSON output, persists rows.

### Worker

`agents/nodes/_clash_worker.py`:

```python
@actor(actor_name="agents.detect_clashes", priority=TaskPriority.HIGH)
async def detect_clashes(
    run_id: UUID,
    federation_id: UUID,
    config: dict,        # group_a/group_b filters, tolerance, severity
) -> None:
    # 1) Fetch the federated IFC bytes.
    # 2) Subprocess ifcclash with the config.
    # 3) Parse the JSON output.
    # 4) For each detected clash:
    #    - Create Clash row (status='open', detected_in_run_id=run_id).
    #    - Skip duplicates: a Clash with the same (project_id, element_a_global_id, element_b_global_id)
    #      already exists → update its status to 'open' if it was 'resolved' more than 30 days ago,
    #      otherwise increment a "re-detected" counter.
    # 5) Emit a node trace event with the count.
```

Use HIGH priority because clash runs gate the rest of the workflow.

### Node

`agents/nodes/detect_clashes.py`:

```python
async def execute(self, ctx, input_data, node_config):
    federation_id = input_data["federation_id"]
    # Spawn the worker and wait for it via the same pattern as sub-workflow node from M4.7.
    job_id = dispatch_task("agents.detect_clashes", run_id=ctx.run_id, federation_id=federation_id, config=node_config)
    await wait_for_job(ctx.session, job_id, timeout=node_config.get("timeout_s", 1800))
    clashes = await Clash.query.where(Clash.detected_in_run_id == ctx.run_id).all()
    return {
        "clash_count": len(clashes),
        "clash_ids": [str(c.id) for c in clashes],
        "by_severity": {"hard": ..., "clearance": ...},
    }
```

### Duplicate handling

The "same clash detected again next week" case is real. M6.3's logic:

- Identify clash by `(project_id, sorted(element_a_global_id, element_b_global_id))`.
- If a row exists with status `'resolved'` or `'ignored'` and the resolution timestamp is recent (≤ 30 days): leave alone, don't re-surface. Helps avoid resolved-clash noise.
- If a row exists with status `'resolved'` and is older than 30 days: bump status back to `'open'` (the as-built may have changed).
- If a row exists with status `'open'`: increment a `times_detected` counter.

Document the 30-day threshold as workspace-configurable in v2; hardcoded for v1.

### Tests

- Clash worker on a known-clash fixture (two intersecting cuboids in a tiny IFC).
- Duplicate handling: detect → resolve → re-detect within 30 days → no re-open; > 30 days → re-open.
- Filter respect: group_a/group_b correctly partition.
- Worker timeout: hangs > timeout → status='failed'.

### Verify

Manual: run the federation+clash workflow on a known-bad coordination model (Schependomlaan has known clashes); expect clash count > 0; the Clashes tab on the project page shows them.

---

## 6.4 — RFI draft + Notify + Extract model properties

Branch: `feat/construction-nodes-rfi-notify-extract`

### "Generate RFI draft" node

LLM-backed. Input: clash_id. Output: `Rfi` row with status='open' (an actual database row, ready for human review).

```python
# agents/nodes/generate_rfi_draft.py
async def execute(self, ctx, input_data, node_config):
    clash = await get_clash(ctx.session, input_data["clash_id"])
    # Prompt template:
    #   "You are a project coordinator drafting an RFI from a coordination clash.
    #    Clash: <discipline_a> element <element_a> vs <discipline_b> element <element_b>
    #    at world position <pos>. Severity: <severity>.
    #    Write a concise RFI (title under 100 chars, body 100–400 words) asking
    #    the responsible designer to resolve. Suggest two possible resolutions."
    result = await llm_extract(provider=node_config["provider"], model=node_config["model"],
                               prompt=render(...), schema=RfiDraftSchema)
    rfi = await create_rfi(
        ctx.session,
        project_id=clash.project_id,
        discipline_id=clash.discipline_a_id,
        clash_id=clash.id,
        title=result.title,
        body=result.body,
        raised_by_id=ctx.system_user_id,  # "Agent" user; see below
        status=RfiStatus.open,
    )
    return {"rfi_id": str(rfi.id), "rfi_number": rfi.number}
```

System user: each workspace has an "Agent" user automatically (lands
in 6.4's migration). It's the `raised_by` for agent-generated RFIs
so the audit trail is honest.

### "Notify discipline lead" node

Looks up the discipline lead (a workspace setting per discipline:
`discipline.lead_user_id`) and dispatches a notification via the
existing `messaging/notification` infrastructure.

```python
# agents/nodes/notify_discipline.py
async def execute(self, ctx, input_data, node_config):
    discipline_id = input_data["discipline_id"]
    payload = node_config["payload_template"]  # CEL-templated against input_data
    lead = await get_discipline_lead(ctx.session, discipline_id)
    if lead is None:
        return {"notified": False, "reason": "no_lead_configured"}
    await create_notification(
        recipient_id=lead.user_id,
        kind="agent_workflow",
        payload=render_template(payload, input_data),
    )
    return {"notified": True, "recipient_id": str(lead.user_id)}
```

Reuses notification fan-out (email, in-app, webhook) that the existing
`messaging/notification` already implements.

### "Extract model properties" node

```python
# agents/nodes/extract_model_properties.py
async def execute(self, ctx, input_data, node_config):
    # input_data: { model_id: UUID, global_id: str (IFC GUID) }
    # Fetches the properties JSONB sibling file (from M3.3) and looks up by GUID.
    props = await fetch_element_properties(input_data["model_id"], input_data["global_id"])
    return {"properties": props, "found": props is not None}
```

No new infrastructure — reuses M3.3's properties-JSON path.

### Tests

- RFI draft node: stub LLM provider; assert it writes a Rfi row with linked clash_id.
- Notify node: no discipline lead → returns `notified=false`; with lead → notification row created.
- Extract: known GUID → properties; unknown GUID → `found=false`.

---

## 6.5 — Site walk capture + Deliverable check

Branch: `feat/construction-nodes-sitewalk-deliverable`

### "Site walk capture" node

Input: photo (document_id) + voice transcript (str). Output: work
items + markup pins on the relevant board.

Architecture:

1. LLM (structured output) extracts list of issues from the
   transcript, each tagged with severity + suggested discipline +
   optional location keywords.
2. For each issue: create a `WorkItem` (existing kept slice of
   `projects/`) tagged with the discipline and a label `"site-walk"`.
3. If the transcript mentions a markup board (e.g., "this is on
   the 3rd floor plan"), create a markup pin on that board at a
   default position (engineer drags it to the right spot later).

Reuses LLM extraction from M4.4 + the existing work item creation
path.

### "Check deliverable" node

Input: deliverable_id. Validates the submitted document against the
deliverable's `spec_json`:

- `required_scale: "1:100"` — extract the PDF's scale annotation (via metadata in M2's PDF underlay code path, or via `pdfjs-dist` text extraction); compare.
- `required_units: "mm"` — same approach.
- `required_sheet_count: 4` — count pages.
- `naming_convention: "A-XX-NN-RV"` — regex against the document's filename.

Spec checks fail → status='rejected' with `reasons[]`. Pass → status='in_review' (humans still need to approve).

```python
# agents/nodes/check_deliverable.py
async def execute(self, ctx, input_data, node_config):
    deliverable_id = input_data["deliverable_id"]
    deliverable = await get_deliverable(ctx.session, deliverable_id)
    if deliverable.submitted_document_id is None:
        return {"passed": False, "reasons": ["no_submission"]}
    checks = run_deliverable_checks(deliverable.spec_json, deliverable.submitted_document_id)
    if all(c.passed for c in checks):
        await update_deliverable_status(ctx.session, deliverable, DeliverableStatus.in_review)
        return {"passed": True, "checks": [c.dict() for c in checks]}
    await update_deliverable_status(ctx.session, deliverable, DeliverableStatus.rejected)
    return {"passed": False, "reasons": [c.reason for c in checks if not c.passed]}
```

### Tests

- Site walk capture: stub LLM, assert N work items created with right discipline.
- Deliverable check: each spec rule (scale, units, sheet count, naming) — pass + fail cases.

---

## 6.6 — Canonical workflows + pin tightening

Branch: `feat/construction-canonical-workflows`

### Goal

Four workflows ship as starter templates a workspace admin can
import in one click. Plus: tighten M3.6's `ClashPinElement.label`
and `RfiPinElement.label` from free-form strings into real
`clashId` / `rfiId` UUIDs now that the Coord chamber exists.

### Starter templates

`server/rapidly/agents/templates/` ships four JSON files. Each is a
complete `graph_json`. The UI surfaces a "Import template" action on
the workflows list (M5.1's surface).

```
templates/
├── 01_daily_clash_sweep.json
├── 02_deliverable_submission.json
├── 03_site_walk_to_punch_list.json
└── 04_drawing_change_log.json
```

#### 01 Daily clash sweep

```
Schedule trigger (daily 06:00)
  → Federate models (workspace's main federation)
  → Detect clashes (config: hard + clearance, tolerance 5mm)
  → Branch (clash_count > 0)
      ↓ yes
      → Loop over clashes
          → Generate RFI draft (per clash)
          → Notify discipline lead (per RFI's discipline)
      → End (notify success)
      ↓ no
      → End (no-clash notify)
```

#### 02 Deliverable submission

```
Webhook trigger
  → Check deliverable
  → Branch (passed)
      ↓ yes
      → Human-in-loop (discipline lead approves) → Update status → End
      ↓ no
      → Notify submitter with reasons → End
```

#### 03 Site walk → punch list

```
Webhook trigger (mobile upload: photo + transcript)
  → Site walk capture
  → Loop over generated work items
      → Notify discipline lead for the work item's discipline
  → End
```

#### 04 Drawing change log

```
Schedule trigger (every Monday 08:00)
  → List documents updated in the last week (HTTP node against own API)
  → Loop over updates
      → LLM diff summary (M4.4 structured output, "What changed in this drawing?")
      → Filter: changes that affect open RFIs (Branch on overlap with rfi.markup_element_id geometry)
      → Notify affected discipline leads
  → End
```

### Pin tightening (M3.6 → M6.6)

Migration walks existing `ClashPinElement.label` rows; for each,
attempt to find a matching `Clash` by the project + label heuristic
(label might be the clash number); if found, replace `label` with
`clashId`. Same for `RfiPinElement.label` → `rfiId`. Pins that don't
match anything keep their free-form label as a `legacyLabel` field
for human review.

Element schema after this PR:

```ts
interface ClashPinElement extends BaseElement {
  type: 'clash-pin'
  modelId: string
  worldPosition: [number, number, number]
  clashId: string             // ← was `label: string` in M3.6
  legacyLabel?: string        // present only for pins migrated from M3.6
}

interface RfiPinElement extends BaseElement {
  type: 'rfi-pin'
  modelId: string
  worldPosition: [number, number, number]
  rfiId: string
  legacyLabel?: string
}
```

### Templates import flow

In `clients/apps/web/src/components/Agents/WorkflowList.tsx`: add
"Import template" button next to "New workflow." Opens modal showing
the four templates with descriptions; clicking one POSTs the JSON to
`POST /api/workflows/import-template` (new endpoint in this PR).
The endpoint creates a new Workflow + initial WorkflowVersion with
the template's graph_json.

### Tests

- Each template imports cleanly: loads the JSON, validates the graph (cycle check, orphan check), creates a workflow + version.
- Each template runs successfully against fixtures (e.g., a known-clash IFC for #01, a known-good deliverable for #02).
- Pin migration: assert tightened pins point at real Clash / Rfi rows; assert unmatched pins keep `legacyLabel`.

### Verify

Manual: as a fresh workspace admin, click "Import template" → daily clash sweep, schedule it, trigger manually, watch a real Clash row + Rfi draft + Notification appear.

---

## 7. Acceptance for M6 as a whole

After 6.1–6.6 land:

- [ ] **Coord chamber entities live.** Disciplines, clashes, rfis, deliverables, approvals all CRUD-able via UI and API.
- [ ] **Project page has Clashes / RFIs / Deliverables tabs.**
- [ ] **Federation workflow end-to-end.** Upload arch + struct IFCs, federate, detect clashes, real `Clash` rows land.
- [ ] **RFI draft node generates a real Rfi row** with the originating clash linked.
- [ ] **Notify node uses existing notification fan-out.**
- [ ] **Deliverable check enforces spec_json rules.**
- [ ] **Site walk capture produces work items + (optionally) markup pins.**
- [ ] **Four starter templates import + run cleanly** in a fresh workspace.
- [ ] **M3.6 pins migrated to real entity refs.**
- [ ] **No-attribution `scan` job green on every M6 PR.**
- [ ] **Memory updated.** `project_m6_construction_layer_complete.md` written. Pivot memory's Coordination-chamber line annotated `[LANDED 2026-MM-DD]`.

---

## 6. Per-PR Definition of Done (M6 flavor)

```markdown
## Definition of Done — M6 construction

### Surface added
- Entities / nodes / templates: <names>
- New deps: <package@version or none>
- Migrations: <names>
- Routes: <new endpoints>

### Verification
- [ ] `uv run task lint && lint_types && test_fast && openapi_export` green
- [ ] `pnpm typecheck && pnpm lint && pnpm test` green
- [ ] `pnpm playwright test <new spec>` green
- [ ] `uv run alembic upgrade head && downgrade -1 && upgrade head` round-trips
- [ ] No-attribution `scan` job green
- [ ] If the PR introduces an IfcOpenShell subprocess: stress-tested with a 250 MB IFC fixture without OOM-killing the API

### Construction correctness
- [ ] Clash detection on a known-bad fixture produces the expected count
- [ ] RFI numbers auto-increment per project without collisions under concurrent creates
- [ ] Deliverable spec_json rules enforced
- [ ] Discipline lead lookup honours workspace settings

### Clean-room compliance
- [ ] Construction-node implementations are ours; no upstream's clash-detection code consulted (we use IfcOpenShell's CLI, which is fine — that's a public OSS tool, not a vendor product's internals)
- [ ] No naming the upstream agent project in any artifact
```

---

## 8. Rollback

Each M6 PR is its own commit on main.

- 6.1: revert + `downgrade()` drops 5 tables. Project tabs disappear.
- 6.2: revert + `downgrade()` drops `federations`. XKT files in S3 stay (cheap).
- 6.3: revert; Clash rows already in DB stay (no schema change). The node simply disappears from the runtime.
- 6.4: revert; new nodes disappear. The "Agent" system user stays in DB.
- 6.5: revert; new nodes disappear.
- 6.6: revert + `downgrade()` restores the M3.6 free-form pin labels (the migration's downgrade copies `clashId` → `label`).

---

## 9. After M6

`MEMORY.md` updates:

- Add `[M6 construction layer complete (YYYY-MM-DD)](project_m6_construction_layer_complete.md)`. Body: lists the 5 Coord entities, the 7 new construction nodes, the 4 starter workflows, and notes that the M3.6 pin tightening is done.
- Annotate the pivot memory's "Coordination" line as `[LANDED 2026-MM-DD]`.

Next milestone: **M7 — Construction integrations (3 weeks).** Bentley
ProjectWise, Autodesk ACC, Aconex, plus formalised MCP server
hosting for LLM-tool extension. Plan in `M7_EXECUTION.md` on user
go-ahead.

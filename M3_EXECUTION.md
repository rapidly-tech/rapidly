# M3 — Self-hosted 3D viewer + IFC ingestion

Executable plan for milestone M3 of `RAPIDLY_ENGINEERING_SUITE_PLAN.md`.
M3 builds the third top-level surface of the engineering suite (per
Framing B): a self-hosted 3D viewer that ingests IFC, lets engineers
navigate federated models, and embeds 3D viewports inside markup
boards so RFI/clash pins land at real world coordinates.

**Read M0 + M1 + M2 first.** M3 assumes the Markup chamber is
renamed (M1.4 landed), engineering primitives exist (M2 landed),
and the no-attribution gate is live (M0).

## Scope decisions (locked)

- **Viewer library: xeokit-sdk under MIT (community edition).** Per the user pivot memory ("Model viewers and IFC tooling must be self-hosted, OSS-licensed"), the MIT core is mandatory. The commercial license (the strategic plan's open decision §11/1) is **not** purchased; we live with the MIT terms. Practical impact: no vendor support, but the source is ours forever.
- **Server-side parsing: IfcOpenShell** (LGPL-3.0 — distinct linkage; we use it via subprocess + the `ifcopenshell` Python package, not by static-linking into our process, so LGPL is comfortable).
- **Storage: existing `catalog/file/` S3 multipart upload.** IFC bytes ride the existing pipeline; new metadata lives in `models/federated_model.py`.
- **3D Viewer is its own top-level chamber.** Per Framing B, the suite leads with Markup + Agents + **3D Viewer**. The chamber surface lives at `/viewer/`; the `ModelViewportElement` embeds it inside a markup board.

## Scope (6 PRs, ~3 weeks)

| # | Branch | What | Backend? | Frontend? |
|---|---|---|---|---|
| 3.1 | `feat/viewer-ifc-ingestion` | IfcOpenShell worker, `FederatedModel` + `ModelDiscipline` tables, S3 ingestion, XKT generation | yes | tiny (upload UI) |
| 3.2 | `feat/viewer-chamber` | `/viewer/` route, model picker, xeokit canvas, basic navigation | small (list API) | yes |
| 3.3 | `feat/viewer-tree-properties` | IFC element tree, properties panel, search-by-property | yes (element lookup API) | yes |
| 3.4 | `feat/viewer-section-measure` | section planes + measurement tool (3D distances in engineering units) | none | yes |
| 3.5 | `feat/markup-model-viewport-element` | `ModelViewportElement` for embedding the viewer inside a markup board | none | yes |
| 3.6 | `feat/viewer-clash-rfi-pins` | click in 3D → place markup pin at world coord; link to markup board | small (pin entity) | yes |

Each PR ships its own tests, stamps the Definition-of-Done block in §5.

## Conventions

- Shell snippets assume the repo root as `pwd`.
- Branches off freshly-pulled `main`. Do not stack.
- Backend pre-push: `cd server && uv run task lint && uv run task lint_types && uv run task test_fast`. Plus `uv run task openapi_export` if routes changed.
- Frontend pre-push: `cd clients/apps/web && pnpm typecheck && pnpm lint && pnpm test` and the relevant Playwright spec.
- Per-PR DoD block in §5.

---

## 3.1 — IFC ingestion (backend)

Branch: `feat/viewer-ifc-ingestion`

### Goal

An engineer uploads an IFC file. A worker parses it, stores metadata
(disciplines, units, world bounding box, element count), and
generates the XKT file that the xeokit viewer loads in 3.2.
Synchronous-feeling: the upload returns immediately; a Dramatiq
worker handles the heavy lift; the UI polls the model's status.

### Domain model

New module: `server/rapidly/viewer/`. Conventions per `server/CLAUDE.md`.

```
server/rapidly/viewer/
├── __init__.py
├── api.py
├── actions.py
├── queries.py
├── types.py
├── permissions.py
├── workers.py
└── ordering.py
```

New ORM rows (under `server/rapidly/models/`):

```python
# models/federated_model.py
class FederatedModel(BaseEntity, SoftDeleteMixin):
    __tablename__ = "federated_models"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="cascade"))
    name: Mapped[str] = mapped_column(String(256))
    source_file_id: Mapped[UUID] = mapped_column(ForeignKey("files.id"))
    xkt_file_id: Mapped[UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    status: Mapped[ModelStatus]  # enum: 'uploaded', 'parsing', 'ready', 'failed'
    units: Mapped[str | None] = mapped_column(String(8))  # 'mm', 'm', 'ft', 'in'
    element_count: Mapped[int | None]
    bbox: Mapped[dict | None] = mapped_column(JSONB)  # {min: [x,y,z], max: [x,y,z]}
    error_message: Mapped[str | None] = mapped_column(Text)

# models/model_discipline.py
class ModelDiscipline(BaseEntity):
    __tablename__ = "model_disciplines"
    model_id: Mapped[UUID] = mapped_column(ForeignKey("federated_models.id", ondelete="cascade"))
    name: Mapped[str] = mapped_column(String(64))  # 'architecture', 'structure', 'MEP', 'civil', ...
    element_count: Mapped[int]
```

### Worker

`server/rapidly/viewer/workers.py`:

```python
@actor(actor_name="viewer.parse_ifc", priority=TaskPriority.LOW, max_retries=2)
async def parse_ifc(model_id: UUID) -> None:
    # 1) Stream the IFC bytes from S3 to a temp file (don't load into memory).
    # 2) Subprocess: `IfcConvert <ifc> <xkt> --json-meta` (xeokit's ifc2xkt CLI).
    #    Subprocess on purpose — IfcOpenShell is memory-hungry and we want it
    #    in its own address space so an OOM kills the worker, not the API.
    # 3) Parse the produced metadata JSON to extract units, element count,
    #    bbox, discipline split.
    # 4) Upload the XKT to S3 via the existing catalog/file path.
    # 5) Update FederatedModel.status = 'ready', xkt_file_id, units, bbox.
    # On any exception: status = 'failed', error_message = <truncated str(e)>.
```

The Dramatiq retry policy is set to 2 — IFC parses that fail twice
in a row are almost certainly malformed input, not transient. Memory
limit on the worker container per the M3-deploy note in §3.1.4.

### Routes (in `viewer/api.py`)

```
POST   /api/viewer/models                  # create FederatedModel; returns presigned upload URL
POST   /api/viewer/models/{id}/complete    # mark upload complete, fan out to parse worker
GET    /api/viewer/models                  # list (paginated, filterable by project_id)
GET    /api/viewer/models/{id}             # one model + disciplines
DELETE /api/viewer/models/{id}             # soft delete
GET    /api/viewer/models/{id}/xkt-url     # presigned download URL for the XKT (used by the frontend canvas)
```

`POST /complete` is the chokepoint where the worker fires. Don't fire
the worker on upload-start — the user might abandon the multipart
upload and we'd waste worker time.

### Permissions

Project-member role required for read; project-admin for create/delete.
Pattern matches `projects/deploy_board/actions.py:_ensure_admin` —
copy the chokepoint shape.

### Migration

```bash
cd server
uv run alembic revision -m "add federated_models and model_disciplines tables"
```

### Container changes

IfcOpenShell needs `apt-get install ifcopenshell-tools` (or build from source — the apt path is faster). Update the worker Dockerfile:

```dockerfile
# server/Dockerfile.worker (or wherever the worker image is built)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ifcopenshell-tools \
    && rm -rf /var/lib/apt/lists/*
```

Also: bump the worker container's memory limit to ~4 GB (small IFC
~500 MB parse; medium IFC ~2 GB; large IFC ~4 GB+). Set in
`server/docker-compose.yml`:

```yaml
services:
  worker:
    mem_limit: 4g
```

Document the size ceiling: any IFC > 500 MB should chunk through
discipline-level federation (split arch/struct/MEP into separate
uploads, then "federate" them in the viewer). M3's worker doesn't
chunk automatically.

### Verify

```bash
cd server
uv run task test_fast
uv run task openapi_export
# Manual: upload a known-good IFC (sample at /tmp/test.ifc), poll
# /api/viewer/models/{id} every 2s, confirm status moves uploaded → parsing → ready.
```

Sample IFC for testing: download `Schependomlaan.ifc` from buildingSMART's public samples (~5 MB, 4 disciplines, well-known reference).

---

## 3.2 — Viewer chamber (frontend foundation)

Branch: `feat/viewer-chamber`

### Goal

`/viewer/` route in the dashboard. List of federated models for the
current workspace's projects. Click one → opens xeokit-sdk canvas
with the model loaded and basic navigation (orbit, pan, zoom, fit).

### Frontend surfaces

- **Deps:** `pnpm add @xeokit/xeokit-sdk` (MIT). Pin to latest 2.x.
- **Route:** `clients/apps/web/src/app/(authenticated)/dashboard/[workspace]/viewer/` with `page.tsx` (model list) and `[modelId]/page.tsx` (the canvas view).
- **Components:** `clients/apps/web/src/components/Viewer/`:
  ```
  Viewer/
  ├── ViewerCanvas.tsx       # xeokit-sdk mount; takes modelId + initial camera state
  ├── ModelList.tsx          # paginated list with status badges
  ├── ModelUploadDialog.tsx  # file picker → presigned upload → poll status
  ├── CameraControls.tsx     # toolbar (fit, top, front, side, isometric)
  └── ViewerErrorBoundary.tsx
  ```
- **Hooks:** `clients/apps/web/src/hooks/viewer/`:
  ```
  useFederatedModelList.ts
  useFederatedModel.ts        # polls until status='ready'
  useUploadFederatedModel.ts  # presigned-PUT, then POST /complete
  useXktUrl.ts                # fetches the presigned download URL
  ```
- **xeokit-sdk lazy load.** The SDK is heavy (~2 MB minified). Lazy-load via `next/dynamic` so the dashboard's other tabs don't pay the cost:
  ```ts
  const ViewerCanvas = dynamic(() => import('@/components/Viewer/ViewerCanvas'), { ssr: false })
  ```
- **xeokit worker.** The SDK ships a XKT decoder worker. Same constraints as `pdfjs-dist` from M2.1 — serve same-origin, verify staging deploy.

### Canvas integration shape

```tsx
// ViewerCanvas.tsx
import { Viewer, XKTLoaderPlugin, CameraMemento } from '@xeokit/xeokit-sdk'

export function ViewerCanvas({ modelId, initialCamera }: Props) {
  const xktUrl = useXktUrl(modelId)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const viewerRef = useRef<Viewer | null>(null)

  useEffect(() => {
    if (!xktUrl || !canvasRef.current) return
    const v = new Viewer({ canvasElement: canvasRef.current, transparent: true })
    const xkt = new XKTLoaderPlugin(v)
    const model = xkt.load({ id: modelId, src: xktUrl })
    viewerRef.current = v
    if (initialCamera) new CameraMemento().restore(v.scene.camera, initialCamera)
    return () => { v.destroy() }
  }, [xktUrl, modelId, initialCamera])

  return <canvas ref={canvasRef} className="h-full w-full" />
}
```

Real code is uglier (cleanup, error handling, fit-to-view on first render); the shape above is the contract.

### Nav

Add a "3D Viewer" entry to the dashboard sidebar (mount point: search the sidebar for the existing "Markup" or "Projects" entry; add adjacent). This satisfies the Framing B promise that the suite leads with three product surfaces.

### Tests

- Unit: `useFederatedModelList` polling behavior with msw.
- Integration: `markup-viewer.spec.ts` — upload a tiny IFC fixture, wait for status=ready, navigate to `[modelId]`, assert the canvas mounts and a `model-loaded` event fires within 5 s.

### Verify

```bash
cd clients/apps/web
pnpm typecheck && pnpm lint && pnpm test
pnpm playwright test viewer-chamber.spec.ts
pnpm build  # confirm bundle size — main bundle should NOT include xeokit
```

Manual smoke: upload Schependomlaan.ifc, watch the model render, orbit/pan/zoom.

---

## 3.3 — Tree + properties panels

Branch: `feat/viewer-tree-properties`

### Goal

Side panels: a tree view of the IFC structure (storeys → spaces →
elements) and a properties panel that shows IFC properties of the
clicked element.

### Backend

xeokit-sdk ships a `TreeViewPlugin` and a `StoreyPlugin` — the tree
itself is client-side, derived from the loaded XKT. **But** rich IFC
properties (Pset_*, custom property sets, materials) are stripped
from the XKT for size reasons. So:

- New table `model_elements` is **not** added in M3 (overkill).
- Instead: store the full IFC element metadata in a per-model JSONB
  blob in S3 (produced by the worker in 3.1, sibling file to the
  XKT). Index by `globalId` on the client.
- New route: `GET /api/viewer/models/{id}/properties-url` returns
  the presigned download URL for that JSONB.
- Client lazy-loads + memoizes the properties JSON; first click
  pays the fetch, subsequent clicks are instant.

### Frontend

- `Viewer/StructureTree.tsx` — uses xeokit's `TreeViewPlugin` with the project hierarchy mode.
- `Viewer/PropertiesPanel.tsx` — shows the clicked element's IFC properties grouped by property set.
- `Viewer/SearchByProperty.tsx` — keyword search across the lazy-loaded properties JSON; result rows pulse the matching element in the canvas (xeokit's `objectStates`).

### Verify

```bash
pnpm test && pnpm playwright test viewer-tree.spec.ts
```

Manual: click a wall, see its `IfcWallStandardCase` properties; search "fire-rated", see only fire-rated elements highlight.

---

## 3.4 — Section planes + measurement

Branch: `feat/viewer-section-measure`

### Goal

Two tools that turn the chamber into a real coordination tool:

- **Section planes:** drop a plane, drag its position/normal, hide everything behind it. Multiple planes intersect (logical AND).
- **Measurement:** click two points → render a 3D distance in the board's engineering units.

### Implementation

- Section: xeokit's `SectionPlanesPlugin`. Wrap in our `Viewer/SectionTool.tsx` with a UI for plane list + toggles.
- Measurement: xeokit's `DistanceMeasurementsPlugin`. Configure its label formatter to use the same `makeFormatter(boardScale)` we built in M2.4 — engineers see "5.234 m" not "5234 mm" if they prefer m units.
- Per-model unit preference: read from `FederatedModel.units` if set, else default to the engineer's profile preference.

### Tests

Mostly visual smoke — Playwright with `toHaveScreenshot()` for two section-plane states and one measurement label.

### Verify

```bash
pnpm playwright test viewer-section-measure.spec.ts
```

Manual: section through a building at floor 2, measure the height of a doorway.

---

## 3.5 — `ModelViewportElement` (markup integration)

Branch: `feat/markup-model-viewport-element`

### Goal

Engineer is on a markup board. They click "Insert 3D viewport," pick
a federated model, draw a rect on the board. That rect becomes a
live xeokit viewer locked to the rect's bounds. They can save camera
state per-element so reopening the board restores the same view.

### Element type

Extend `clients/apps/web/src/utils/markup/elements.ts` (already
extended in M2 with `pdf-underlay` and `image-underlay`):

```ts
interface ModelViewportElement extends BaseElement {
  type: 'model-viewport'
  modelId: string
  /** Saved camera state (from `new CameraMemento().save(scene.camera)`). */
  cameraJson: object
  /** Section plane configurations carried into the embedded view. */
  sectionPlanes: SectionPlaneSpec[]
  /** Element-local rect is BaseElement's x/y/width/height. */
}
```

### Painter

Distinct from other element painters: this one is **not** drawn on
the canvas, it's an HTML overlay positioned at the element's
screen-space bounds. The renderer leaves a transparent hole at the
element's location; a sibling React component mounts a `<ViewerCanvas>`
positioned with the same bounds (via the existing technique used by
`EmbedsOverlay.tsx`).

Pan/zoom of the markup board re-positions the overlay. When the
element scrolls off-screen, the embedded viewer is `display: none`'d
to free GPU memory (and re-mounted on scroll-back).

### Tool

"3D viewport" button in the markup toolbar. Click → modal: pick a
federated model from the workspace. → Draw rect → element created.

### Save state

When the user changes the camera or section planes inside an
embedded viewer, debounce the save (1000 ms) and write back to the
Yjs element's `cameraJson` / `sectionPlanes`. Other peers see the
updated camera within ~1 s.

### Tests

- Painter test for the "hole" technique (canvas leaves the bounds untouched; overlay component renders at the same rect).
- Yjs save-debounce test with fake timers.

### Verify

Manual: insert two viewports on the same board, set different cameras, reload the board, confirm cameras persist and are independent.

---

## 3.6 — Clash & RFI pin placement from 3D

Branch: `feat/viewer-clash-rfi-pins`

### Goal

Pin tools that bridge the 3D viewer back into the markup chamber:
click a point in 3D → place a markup pin at that world coordinate →
the pin appears on every markup board that embeds this model.

### Domain model

Add `ClashPinElement` and `RfiPinElement` to `elements.ts`:

```ts
interface ClashPinElement extends BaseElement {
  type: 'clash-pin'
  modelId: string
  worldPosition: [number, number, number]
  /** Free-form label until M6 introduces a real Clash entity. */
  label: string
}

interface RfiPinElement extends BaseElement {
  type: 'rfi-pin'
  modelId: string
  worldPosition: [number, number, number]
  label: string
}
```

**Note:** in M3 these are markup elements only. The strategic plan
§2.3 introduces real `Clash` and `Rfi` ORM entities in M6
(Coordination chamber). When M6 lands, `label` becomes `clashId` /
`rfiId` (a UUID reference); the migration walks existing pins. For
now: free-form labels keep the surface useful without coupling.

### Tools

In the viewer chamber: "Clash pin" and "RFI pin" buttons. Clicking
the canvas after activating the tool casts a ray (xeokit's
`pick({ canvasPos: [px, py] })`) and reads the world hit position.
Modal asks for the label, then writes the pin to the **currently
active markup board** (an explicit dropdown on the viewer's toolbar
selects which board pins go to).

In a markup board with a `ModelViewportElement` embedded: pins in
the board with a matching `modelId` render as floating 3D markers
inside the embedded viewport. xeokit's `AnnotationsPlugin` handles
the 3D-to-2D projection.

### Tests

- Worldcoord round-trip: place a pin, save board, reload, confirm pin renders at the same screen position from the same camera.
- Multi-viewport test: same board has two `ModelViewportElement`s of the same model — pin appears in both.

### Verify

Manual: place a clash pin on a beam in 3D, switch to the markup
board that owns it, see the pin floating above the beam at the right
spot. Pan the markup board's embedded viewport — pin tracks the
camera.

---

## 4. Acceptance for M3 as a whole

After 3.1–3.6 land:

- [ ] **`/viewer/` route renders.** Models from the workspace's projects list; status badges accurate.
- [ ] **IFC ingestion end-to-end.** Upload Schependomlaan.ifc; status moves uploaded → parsing → ready within ~30 s on a 4 GB worker.
- [ ] **Canvas mounts xeokit and loads XKT.** Orbit/pan/zoom/fit all work; no console errors.
- [ ] **Tree + properties panels populated.** Click an element, see its IFC props grouped by Pset.
- [ ] **Section + measurement tools work.** Engineer-units labels (M2.4 formatter).
- [ ] **`ModelViewportElement` is in the markup element union.** Embed in a board; reload; camera persists.
- [ ] **Clash + RFI pins round-trip** between viewer and markup boards.
- [ ] **No-attribution `scan` job green** on every M3 PR.
- [ ] **Memory updated.** `project_m3_viewer_complete.md` written. The pivot memory's "3D viewer" surface entry annotated `[LANDED 2026-MM-DD]`.
- [ ] **License compliance.** Both xeokit-sdk and IfcOpenShell credited in `clients/apps/web/THIRD_PARTY.md` (or wherever third-party credits live; if absent, create it). LGPL note for IfcOpenShell included.
- [ ] **Bundle size sanity.** `pnpm build` main bundle has grown by < 50 KB (xeokit is lazy-loaded; only Viewer route pays it).
- [ ] **Worker memory.** Stress test with a 250 MB IFC — confirm the worker container peaks under 4 GB and does not OOM-kill.

---

## 5. Per-PR Definition of Done (M3 flavor)

```markdown
## Definition of Done — M3 viewer milestone

### Surface added
- Backend: <dirs, models, routes added>
- Frontend: <components, hooks, routes added>
- New deps: <package@version or none>
- Migration: <new migration filename or none>

### Verification
- [ ] `uv run task lint && lint_types && test_fast` green
- [ ] `pnpm typecheck && pnpm lint && pnpm test` green
- [ ] `pnpm playwright test <new spec>` green
- [ ] `uv run alembic upgrade head && downgrade -1 && upgrade head` round-trips (if migration in this PR)
- [ ] No-attribution `scan` job green
- [ ] OpenAPI client regenerated if routes changed
- [ ] Manual: upload an IFC, load in viewer, confirm the surface added in this PR works

### Quality
- [ ] xeokit-sdk + IfcOpenShell remain MIT/LGPL (no commercial-licensed code lifted)
- [ ] No PII or auth state in the xeokit canvas (annotations, etc. carry no secrets — engineering IP is the data, but it lives in S3 behind workspace auth)
- [ ] Worker memory stays under container limit for the test fixtures
- [ ] Bundle size delta < 50 KB on the main bundle (viewer surface deltas don't count)
```

---

## 6. Rollback

Each M3 PR is its own commit on main.

- 3.1: revert PR + run the migration's `downgrade()` to drop `federated_models` and `model_disciplines`. IFC files in S3 stay (no cleanup; cheap).
- 3.2–3.6: revert PR. No data implications.
- xeokit-sdk + IfcOpenShell deps stay in lockfiles after revert — that's fine; they don't ship without being imported.

---

## 7. After M3

`MEMORY.md` updates:

- Add `[M3 viewer complete (YYYY-MM-DD)](project_m3_viewer_complete.md)` summarizing: chamber lives at `/viewer/`, IFC ingestion via IfcOpenShell worker, xeokit-sdk MIT, `ModelViewportElement` embeds inside markup, clash/RFI pins as markup elements (pre-M6 placeholder for the real Clash/Rfi entities).
- Annotate the pivot memory's "3D viewer" line as `[LANDED 2026-MM-DD]`.

Next milestone: **M4 — Agent runtime backend (4 weeks).** New domain
`server/rapidly/agents/` with submodules `workflow`, `node`,
`execution`, `dataset`, `eval`, `rag`, `trace`, `credential`. Node
catalog v1 (LLM, HTTP, code, branch, loop, RAG search, structured
output, human-in-loop, sub-workflow, file read/write). Plan in
`M4_EXECUTION.md` on user go-ahead.

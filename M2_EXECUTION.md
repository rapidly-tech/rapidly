# M2 — Engineering primitives in the Markup chamber

Executable plan for milestone M2 of `RAPIDLY_ENGINEERING_SUITE_PLAN.md`.
M2 adds the four primitives that turn the markup chamber into an
engineering markup surface: PDF underlay, image underlay, scale
calibration, and engineering-units dimensions.

**Read M0 + M1 first.** M2 assumes the no-attribution gate is live,
the abandoned PRs are closed, and `sharing/collab/` has been renamed
to `sharing/markup/` (M1.4). All paths below use the post-M1.4
filenames. If you're executing M2 before M1.4 lands, every
`sharing/markup/` becomes `sharing/collab/` and every `Markup/`
becomes `Collab/` — but don't do that: ship M1.4 first so the
renamed surface is stable before M2 lands on top.

## Scope (Framing B)

No Documents chamber, no durable storage with versioning + ACL. PDFs
and images upload to the existing markup asset store (the same one
that backs `ImageElement`); they live within the board. This matches
the "Markup + Agents + 3D viewer" suite-level pitch — engineers'
async document workflow stays in Aconex/SharePoint/BIM360.

| # | Branch | What | New deps |
|---|---|---|---|
| 2.1 | `feat/markup-pdf-underlay` | `PdfUnderlayElement` + painter + tool button + tests | `pdfjs-dist` |
| 2.2 | `feat/markup-image-underlay` | `ImageUnderlayElement` (distinct from existing `ImageElement` — see §2.2.1) + painter + tool | none |
| 2.3 | `feat/markup-scale-calibration` | "Calibrate scale" tool — drag a known-length line, type the real length, store world-units-per-pixel on the board | none |
| 2.4 | `feat/markup-engineering-units` | per-board units setting (mm/m/in/ft) + dimensions overlay upgrade to render in chosen units when scale set | none |

Each PR is small (~400–800 LOC), ships with tests, and stamps the
per-PR quality checklist. Backend is untouched in M2 — these are
client-side element types riding the existing Yjs `Y.Map<id, props>`
schema.

## Conventions

- Shell snippets assume the repo root as `pwd`.
- Branches off freshly-pulled `main` after the prior M2 PR merges.
- Pre-push: `cd clients/apps/web && pnpm typecheck && pnpm lint && pnpm test` plus the markup-specific Playwright smoke if it exists in `__tests__/markup.spec.ts`.
- Server-side `cd server && uv run task test_fast` is still required even though no backend code changes — the OpenAPI snapshot and the server-tests fixtures both touch markup signaling, so we verify nothing drifted.
- Every PR stamps the Definition-of-Done block (§4 below).

---

## 2.1 — PDF underlay

Branch: `feat/markup-pdf-underlay`

### Goal

Let an engineer drop a PDF page onto the board as a non-interactive
underlay. They can pan/zoom over it like any other element, draw on
top with the existing markup tools, and the PDF rendering survives
reload via the existing E2EE asset store.

### Surfaces

- **Element type.** Extend `clients/apps/web/src/utils/markup/elements.ts`:
  - Add `'pdf-underlay'` to the `ElementType` union (line 23).
  - Add interface `PdfUnderlayElement extends BaseElement` with fields:
    ```ts
    interface PdfUnderlayElement extends BaseElement {
      type: 'pdf-underlay'
      assetHash: string       // existing markup asset store key
      page: number            // 1-indexed
      /** Natural page width/height at 1× scale, captured at upload. */
      pageWidth: number
      pageHeight: number
    }
    ```
  - Add it to the `MarkupElement` (was `CollabElement`) union near line 221.
  - Add a type guard `export function isPdfUnderlay(el: MarkupElement): el is PdfUnderlayElement`.
- **Painter.** Add a `paintPdfUnderlay` function in `clients/apps/web/src/utils/markup/renderer.ts` paralleling the existing `paintImage`. Use `pdfjs-dist` to render the page into an offscreen canvas keyed by `(assetHash, page)`; cache it in a module-local `Map<string, HTMLCanvasElement>` so subsequent paints skip the work.
- **Asset upload.** Reuse the markup asset upload path (same one `ImageElement` uses). The PDF is content-addressed; the `assetHash` is the storage key. Confirm the existing path accepts `application/pdf`; if not, extend the mime-type allowlist in the upload handler.
- **Tool.** Add a "PDF" button to the toolbar (mount point in `clients/apps/web/src/components/Markup/Whiteboard/PropertiesPanel.tsx` or wherever the existing image-import button lives — grep `image/png` to find it). On click: file picker → upload → for each PDF page, create one `PdfUnderlayElement` laid out side-by-side. Multi-page PDFs become multiple elements (one per page) so each page can be re-positioned independently.
- **Tests:**
  - Unit: `renderer.test.ts` — assert a painted `pdf-underlay` produces correct bounding-box invalidation.
  - Unit: a new `pdf-page-cache.test.ts` for the offscreen-canvas cache (hits, misses, eviction at 100 entries).
  - Integration: `clients/apps/web/__tests__/markup-pdf.spec.ts` — drop a 1-page PDF, reload, confirm the element re-renders.

### Steps

1. `cd clients/apps/web && pnpm add pdfjs-dist`. Pin to the latest 4.x.
2. Add the element type to `elements.ts`. Run `pnpm typecheck` — every `switch (el.type)` in the codebase will burst. Walk the burst: ignore the new type in painters that don't apply, add the new branch where it does (renderer, hit-test, selection bounds, export, search).
3. Implement `paintPdfUnderlay` + the `(assetHash, page)` cache.
4. Wire the upload + tool button.
5. Tests.
6. Manual smoke: drop a 5-page IFC schedule PDF, draw a stroke on page 3, reload the page, confirm everything's where you left it.

### Verify

```bash
cd clients/apps/web
pnpm typecheck && pnpm lint && pnpm test
pnpm playwright test markup-pdf.spec.ts
cd ../../server && uv run task test_fast
```

### Risks / nuances

- `pdfjs-dist` ships a worker (`pdf.worker.min.js`). It must be served same-origin or the worker init fails. Next.js + the existing static asset config supports this; verify by deploying to staging once before merge.
- Large PDFs (>50 MB, hundreds of pages) bring the asset store into a regime the existing UI doesn't really expect. Limit input to PDFs ≤ 100 MB on the client; show "Use Aconex/SharePoint for larger drawings" if exceeded. This matches the Framing B story (we don't compete on big-file workflow).
- E2EE — the asset store encrypts at the browser before upload. PDFs go through the same path; no plaintext on the server. Confirm by inspecting the network tab: the upload body must be ciphertext.

---

## 2.2 — Image underlay

Branch: `feat/markup-image-underlay`

### 2.2.1 Why a separate element type from `ImageElement`

`ImageElement` already exists in the markup chamber. It treats images
as **interactive content** — selectable, resizable, croppable, can
have arrows bound to it, etc.

`ImageUnderlayElement` treats images as **non-interactive substrate** —
locked under the markup, can't be selected by default, can't be
cropped, sits behind all annotation. Same image bytes, different
interaction semantics. The reason to make it a distinct type is that
otherwise every painter and hit-tester has to branch on a boolean
`isUnderlay` field for the same element type, and you end up with two
behaviours hiding under one name.

Cost: small code duplication in the painter (same `ctx.drawImage`
call). Benefit: the rest of the chamber treats underlays as a
first-class category and the selection / properties UI doesn't need
conditional branches.

### Surfaces

- **Element type** in `elements.ts`:
  ```ts
  interface ImageUnderlayElement extends BaseElement {
    type: 'image-underlay'
    assetHash: string
    naturalWidth: number
    naturalHeight: number
  }
  ```
  Add type guard.
- **Painter** — copy the body of `paintImage` minus the crop/binding paths, name it `paintImageUnderlay`. Always painted in the first compositing layer (under all other element types).
- **Layer ordering** — confirm `renderer.ts` sorts elements by a `z` field or by array order; underlays go to the bottom of the stack regardless of insertion order. If sort is by z, set `z = -1e9` on insert. If it's array order, splice underlays to index 0 on insert and keep them there.
- **Hit-test** — `getElementAtPoint` returns `null` for `image-underlay` unless a modifier key (Alt) is held. This makes the underlay non-interactive by default.
- **Tool** — "Image underlay" button next to the "PDF" button from 2.1. File picker → upload → place at canvas center, 1:1 natural size.
- **Tests:**
  - Painter test for layering invariant.
  - Hit-test test for "underlay is unselectable without Alt".

### Steps

Mechanical. Mirror 2.1. ~200 LOC + tests.

### Verify

Same as 2.1 minus the `pnpm add`.

---

## 2.3 — Scale calibration

Branch: `feat/markup-scale-calibration`

### Goal

Engineer drops a PDF or image underlay of a drawing, then calibrates
it: "this line on the drawing is 5.000 m long." From then on, every
length the dimensions overlay reports for elements on this board is
in real-world units, not pixels.

### Data model

Add to the board's Yjs root map (not on any element):

```ts
interface BoardScale {
  /** World units per canvas pixel at zoom=1. */
  unitsPerPixel: number
  /** Unit symbol stored as a hint for the formatter. */
  unit: 'mm' | 'm' | 'in' | 'ft'
}
```

The root map already holds per-board state (existing settings). Add
a `scale: BoardScale | null` key.

### Tool flow

1. User clicks "Calibrate scale" in the toolbar.
2. Cursor turns into a crosshair. User drags a line over a feature whose length they know.
3. Modal appears: "How long is this line in real units?" with a number input + unit dropdown (mm/m/in/ft).
4. On confirm: compute `unitsPerPixel = realLength / pixelLength` (where `pixelLength = √((x2-x1)² + (y2-y1)²)`), persist to the board's Yjs root map.
5. From here on, the dimensions overlay (§2.4) renders in real units.

### Surfaces

- **State.** `clients/apps/web/src/utils/markup/board-state.ts` (or wherever the Yjs root map is wrapped) — add `scale: BoardScale | null` accessor + setter. Setter broadcasts the change so all peers see the new scale instantly.
- **Tool.** `clients/apps/web/src/components/Markup/Whiteboard/Tools/CalibrateScale.tsx` — drag handler + modal. Hooks into the existing tool registry (grep `registerTool` in the chamber to find it).
- **No new element type.** The calibration line is ephemeral — it disappears once the modal commits. Stored data is the scale on the board, not the line.
- **Tests:**
  - Unit test for `unitsPerPixel` math, including the negative-coordinate edge case.
  - Integration: drag a line, type 1000, choose mm, assert `board.scale.unitsPerPixel === 1000 / pixelLength`.

### Verify

```bash
cd clients/apps/web
pnpm typecheck && pnpm lint && pnpm test
pnpm playwright test markup-calibrate.spec.ts
```

Manual smoke: drop a known-scale PDF (e.g., a 1:100 architectural plan), calibrate via a 5m wall, draw a rectangle, confirm the dimensions overlay reads "5.00 m × 3.00 m" not "500 × 300".

---

## 2.4 — Engineering-units dimensions overlay

Branch: `feat/markup-engineering-units`

### Goal

Extend the existing `dimensions-overlay.ts` so its `"W × H"` labels
render in the board's units when a scale is set, and stay in pixels
when no scale is set (the existing behaviour, preserved).

### Surfaces

- **Formatter.** Add `clients/apps/web/src/utils/markup/units.ts` with:
  ```ts
  export interface UnitFormatter {
    format(pixels: number): string  // "1.234 m" or "1234.0 px"
  }

  export function makeFormatter(scale: BoardScale | null): UnitFormatter
  ```
  - When `scale === null`: returns "<N> px" with the existing precision.
  - When `scale !== null`: multiplies by `scale.unitsPerPixel`, picks a precision based on the unit (mm: 0 decimals; m: 2 decimals; in: 2 decimals; ft: 1 decimal + inches; ft is the gnarly one — defer to two-line label "5'-3"" via existing precedent or skip for v1).
- **`dimensions-overlay.ts`** — accept a `getFormatter` option in `DimensionsOverlayOptions`, default to the pixel formatter for backwards-compat with tests. Use it in `dimensionLabels` instead of the hardcoded "px" output.
- **Per-board unit settings UI.** Small dropdown in the board's settings menu (mount point: `clients/apps/web/src/components/Markup/Whiteboard/PropertiesPanel.tsx`) — "Units: mm | m | in | ft". Changes the board's `scale.unit` if a scale is set, no-op otherwise.
- **Tests:**
  - Formatter unit tests for each unit and for the `null` (pixel) fallback.
  - Existing `dimensions-overlay.test.ts` updated to pass a formatter; the test for "px" output stays as the pixel-formatter case.

### Verify

```bash
cd clients/apps/web
pnpm typecheck && pnpm lint && pnpm test
pnpm playwright test markup-dimensions-units.spec.ts
```

Manual: calibrate a board to 1:100 mm/pixel, draw a rectangle, see "5000 mm × 3000 mm". Flip the board to m units, see "5.00 m × 3.00 m". Drop the scale (a button to "Clear scale"), see "<N> px" again.

---

## 3. Acceptance for M2 as a whole

After 2.1–2.4 land:

- [ ] **Element model extended.** `elements.ts` has `pdf-underlay` and `image-underlay` in its union; type guards present; tests pass.
- [ ] **`pdfjs-dist` is the only new dep.** `git diff main -- clients/apps/web/package.json` shows exactly one addition.
- [ ] **Asset store accepts PDF.** mime-allowlist updated; the upload path E2EE-encrypts before upload (verified by network inspection).
- [ ] **Board has a `scale` field.** Round-trips via Yjs (open two browsers, calibrate in one, see the scale apply in the other).
- [ ] **Dimensions overlay supports units.** Engineering units render when scale is set; pixels otherwise.
- [ ] **All M2 PRs landed the no-attribution `scan` job green.**
- [ ] **Memory updated.** Add `project_m2_markup_primitives_complete.md` summarizing what landed. Annotate `project_collab_excalidraw_rewrite.md` with `[EXTENDED FOR ENGINEERING USE 2026-MM-DD — see project_m2_markup_primitives_complete.md]`.
- [ ] **End-to-end engineering workflow possible.** Drop a 1:100 plan PDF, calibrate scale via a known dimension, mark up RFI annotations with real-world measurements, reload, confirm everything persists.

---

## 4. Per-PR Definition of Done (M2 flavor)

```markdown
## Definition of Done — M2 markup primitive

### Surface added
- Element type / overlay / tool: <name>
- New deps: <package@version or none>
- File mutations: <files added / changed>
- Tests added: <files>

### Verification
- [ ] `pnpm typecheck` green
- [ ] `pnpm lint` green
- [ ] `pnpm test` green
- [ ] `pnpm playwright test <new spec>` green
- [ ] `cd server && uv run task test_fast` green (OpenAPI snapshot stable)
- [ ] No-attribution `scan` job green
- [ ] Manual: open in two browsers, exercise the new primitive, confirm Yjs sync

### Quality
- [ ] No new `any` types in element model
- [ ] No new top-level conditional branches in painters beyond the new element type's case
- [ ] Hit-test, selection bounds, export, search all aware of the new element type (or explicitly skip it with a comment)
- [ ] Asset uploads still go through the E2EE path; confirmed via network tab
```

---

## 5. Rollback

Each M2 PR is its own commit on main. Rollback by `gh pr create` of a
revert. No DB schema changes in M2, so no migration to back out.
Yjs documents created with new element types will silently drop the
unknown types on a downgraded client — log noise but no data
corruption. The scale field on the board's root map is similarly
forward-compatible: an older client ignores unknown root keys.

---

## 6. After M2

`MEMORY.md` updates:

- Add `[M2 markup primitives complete (YYYY-MM-DD)](project_m2_markup_primitives_complete.md)` — body summarizes the four primitives, the new `pdfjs-dist` dep, and the board-`scale` schema addition.
- The `project_collab_excalidraw_rewrite.md` entry: append "M2 extended this with PDF/image underlay + scale calibration + engineering units."

Next milestone: **M3 — Self-hosted 3D viewer.** Three weeks. Adds
xeokit-sdk integration, IFC ingestion (server-side IfcOpenShell),
the `ModelViewportElement` markup type, and per-element world
coordinates so a clash pin can land at `(x, y, z)` in the federated
model. Plan in `M3_EXECUTION.md` on user go-ahead.

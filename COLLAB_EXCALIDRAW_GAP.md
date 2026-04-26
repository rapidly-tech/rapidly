# Collab Whiteboard — Excalidraw Parity Gap Analysis

**Date**: 2026-04-26 · **Method**: clean-room — Excalidraw side from public docs/README/blog only (no source read or copy). Our side from `clients/apps/web/src/components/Collab/` + `clients/apps/web/src/utils/collab/` inventory.

**Per project policy**: AI features (Magic Frame, Wireframe-to-code, Text-to-diagram, BYOK token UIs) are explicitly OUT OF SCOPE. Items marked **AI-skip**.

---

## Legend

- ✅ At parity — both have it.
- 🟡 Partial — we have it, with documented gaps.
- ❌ Missing — Excalidraw has it, we don't.
- ➕ Extra — we have it, Excalidraw doesn't.
- 🚫 AI-skip — Excalidraw has it; we will not implement.

---

## 1. Tool palette

| Tool | Rapidly | Excalidraw | Status |
|------|---------|------------|--------|
| Selection | ✅ `tools/select.ts` | ✅ | ✅ |
| Rectangle | ✅ `tools/rect.ts` | ✅ | ✅ |
| Ellipse / circle | ✅ `tools/ellipse.ts` | ✅ | ✅ |
| Diamond | ✅ `tools/diamond.ts` | ✅ | ✅ |
| Arrow | ✅ + arrowhead types `tools/arrow.ts` | ✅ + elbow arrows | 🟡 — no elbow arrows yet |
| Line | ✅ + 45° snap `tools/line.ts` | ✅ | ✅ |
| Free-draw | ✅ + pressure `tools/freedraw.ts` | ✅ | ✅ |
| Text | ✅ contenteditable overlay `tools/text.ts` | ✅ | ✅ |
| Sticky note | ✅ `tools/sticky.ts` | ❌ (Excalidraw has none) | ➕ |
| Hand / pan | ✅ `tools/hand.ts` | ✅ | ✅ |
| **Eraser** | ❌ enum reserved, registry stub `tools/index.ts:33` | ✅ | ❌ |
| Image | 🟡 thumbnails ≤30 KB inline; no asset upload yet | ✅ + crop editor | 🟡 |
| Frame | ✅ data model `elements.ts:162` | ✅ + slide templates | 🟡 — drag-into-frame UI partial |
| Embed (web) | ✅ `EmbedElement` with sandbox + URL allowlist | ✅ + Drive video allowlist | 🟡 — verify allowlist parity |
| **Lasso** | ❌ | ✅ | ❌ |
| **Library / stencil tool** | ❌ | ✅ + libraries.excalidraw.com | ❌ |
| Laser pointer | ✅ `laser.ts` | ✅ | ✅ |
| Magic Frame | 🚫 AI-skip | ✅ | 🚫 |

## 2. Element model / properties

| Property | Rapidly | Excalidraw | Status |
|---|---|---|---|
| `id, type, x, y, width, height, angle` | ✅ `elements.ts:23-35` | ✅ | ✅ |
| `version, versionNonce, isDeleted` | 🟡 `version` only — no `versionNonce` for Y-CRDT | ✅ JSON schema | 🟡 |
| `seed` (rough.js stable jitter) | ✅ | ✅ | ✅ |
| `roughness` (0/1/2) | ✅ | ✅ | ✅ |
| `roundness {type, value}` | 🟡 `roundness` flag, no separate `value` field | ✅ | 🟡 |
| `strokeColor / fillColor / fillStyle / strokeStyle / strokeWidth / opacity` | ✅ | ✅ | ✅ |
| `groupIds[]` (nested groups) | ✅ `groups.ts` | ✅ | ✅ |
| `boundElements` (labels, child IDs) | 🟡 `boundTextId` + Frame `childIds`; no general boundElements list | ✅ | 🟡 |
| `link` (hyperlink) | ✅ + hover badge `hyperlinks.ts` | ✅ | ✅ |
| `locked` | ✅ advisory lock `locks.ts` | ✅ | ✅ |
| `customData` (host-app extension) | ❌ | ✅ | ❌ |
| `files: { [fileId]: { dataURL, mimeType, ... } }` map | 🟡 inline in `ImageElement` only — no top-level files map | ✅ | 🟡 |
| Pen pressure (per-point) | ✅ `FreeDrawElement.pressures[]` | ✅ | ✅ |
| Arrowhead types | ✅ triangle/dot/bar | ✅ + circle, bar, none, etc. | 🟡 — partial set |

## 3. Editing ops

| Op | Rapidly | Excalidraw | Status |
|---|---|---|---|
| Single / shift / marquee select | ✅ | ✅ | ✅ |
| Move, resize (8 handles), rotate | ✅ | ✅ | ✅ |
| Group / ungroup nested | ✅ Cmd+G/Cmd+Shift+G | ✅ | ✅ |
| Copy / paste in-app | ✅ ID-rewrite `clipboard.ts` | ✅ | ✅ |
| **System-clipboard cut/copy/paste** | 🟡 in-app buffer only | ✅ `excalidraw/clipboard` MIME | 🟡 |
| Undo / redo | ✅ scoped to ORIGIN_LOCAL `undo.ts` | ✅ + `CaptureUpdateAction` enum | 🟡 — no public capture-mode API |
| Delete | ✅ | ✅ | ✅ |
| **Duplicate (Cmd+D)** | ❌ | ✅ | ❌ |
| **Align (left/center/right/top/middle/bottom)** | ❌ | ✅ | ❌ |
| **Distribute (horizontal/vertical)** | ❌ | ✅ | ❌ |
| **Flip horizontal / vertical** | ❌ | ✅ | ❌ |
| Send to back / front, layer ordering | 🟡 `zIndex` field in model — no UI | ✅ Cmd+Shift+[ / ] | 🟡 |

## 4. Canvas / view

| | Rapidly | Excalidraw | Status |
|---|---|---|---|
| Infinite canvas | ✅ `viewport.ts` | ✅ | ✅ |
| Pan (spacebar / hand / pinch) | ✅ + 2-finger trackpad | ✅ | ✅ |
| Zoom (10–3000%) | ✅ at-cursor | ✅ | ✅ |
| **Zoom-to-fit / zoom-to-selection** | ❌ | ✅ `scrollToContent` API | ❌ |
| Dark mode | ✅ Tailwind `dark:` classes | ✅ `theme: light|dark` prop | ✅ |
| Grid render | ❌ — no visual grid toggle | ✅ `gridModeEnabled` | ❌ |
| **Snap-to-grid / snap-to-objects** | 🟡 alt-drag hint, no full snap engine | ✅ | 🟡 |
| **Zen mode** | ❌ | ✅ | ❌ |
| **View-mode (read-only)** | ❌ | ✅ `viewModeEnabled` | ❌ |
| `viewBackgroundColor` | 🟡 export-side only | ✅ runtime | 🟡 |

## 5. Collaboration

| | Rapidly | Excalidraw | Status |
|---|---|---|---|
| Live cursors | ✅ `cursor-overlay.ts` | ✅ `onPointerUpdate` | ✅ |
| Selection broadcast | ✅ `remote-selection-overlay.ts` | ✅ `collaborators` map | ✅ |
| Named users + colour | ✅ `useDisplayName.ts` | ✅ | ✅ |
| Follow-me / presenter | ✅ one-way viewport lock `follow-me.ts` | ✅ | ✅ |
| **Reactions / raised-hand** | ❌ | ✅ | ❌ |
| **QR-code session join** | ❌ | ✅ | ❌ |
| Room URL / invite | ✅ fragment-based `invitation-fragment.ts` | ✅ | ✅ |
| **Transport** — WebRTC P2P + signaling | ➕ raw WebRTC + COTURN, no third-party room server | ✅ Excalidraw+ hosted | ➕ |
| **CRDT model** | ➕ Yjs (vs. Excalidraw's custom OT) | OT | ➕ different approach |

## 6. Persistence / IO

| | Rapidly | Excalidraw | Status |
|---|---|---|---|
| Local autosave | ✅ IndexedDB ciphertext | ✅ localStorage | ✅ |
| **Cross-tab IndexedDB coordination** | ❌ — single-tab only | n/a | gap |
| JSON export | ✅ `rapidly-collab-v1` schema | ✅ `excalidraw` schema | ➕ different format |
| **JSON import (file picker)** | ❌ — paste only | ✅ `loadFromBlob` | ❌ |
| **`.excalidraw` interop** | ❌ | n/a | ❌ |
| PNG export | ✅ + selection bounds + bg colour | ✅ | ✅ |
| SVG export | 🟡 clean lines (no rough jitter in SVG) | ✅ matches canvas | 🟡 |
| **Lossless round-trip (embed JSON in PNG/SVG)** | ❌ | ✅ | ❌ |
| **Library `.excalidrawlib` files** | ❌ | ✅ + libraries.excalidraw.com integration | ❌ |
| PWA / offline | ✅ service worker | ✅ | ✅ |
| **Read-only share link** | ❌ | ✅ | ❌ |

## 7. Advanced

| | Rapidly | Excalidraw | Status |
|---|---|---|---|
| Mermaid → diagram | ✅ TD/TB/BT/LR/RL parser `mermaid.ts` | ✅ + ER + State diagrams (Mar 2026) | 🟡 — fewer diagram types |
| Hyperlinks | ✅ `hyperlinks.ts` | ✅ | ✅ |
| Frames | ✅ data model | ✅ + slide templates | 🟡 |
| Web embeds (sandboxed iframe) | ✅ `EmbedElement` | ✅ + extended allowlist | 🟡 |
| **Excalifont (CJK)** | ❌ | ✅ | ❌ |
| **Charts (radar, multi-series)** | ❌ | ✅ | ❌ |
| **Crop editor for images** | ❌ | ✅ | ❌ |
| **Background-removal for images** | ❌ | ✅ | ❌ |
| **AI Magic Frame / wireframe-to-code / text-to-diagram** | 🚫 | ✅ | 🚫 AI-skip |
| Command palette (Cmd+K) | ➕ ~50 actions | ❌ Excalidraw has none documented | ➕ |
| Keyboard-shortcut overlay | ✅ `ShortcutsOverlay.tsx` | 🟡 (no documented overlay) | ➕ |
| Mobile pinch / sheet UI | ✅ | ✅ | ✅ |

## 8. Public component API parity

We do NOT publish a `@rapidly/whiteboard` component. Excalidraw's **`@excalidraw/excalidraw`** is a third-party-embeddable React component with `excalidrawAPI`, `updateScene`, `addFiles`, etc.

| | Rapidly | Excalidraw |
|---|---|---|
| Embeddable npm package | ❌ | ✅ |
| `updateScene / getSceneElements / getAppState` | ❌ | ✅ |
| `excalidrawAPI` ref-style | ❌ | ✅ |
| `customData` extension hook | ❌ | ✅ |
| **MCP / programmatic agent API** | 🚫 AI-skip | ✅ (Feb 2026) | 🚫 |

This is intentional — we are an end-user product, not a host SDK. **Recommendation: keep as a non-goal.**

---

## Summary

**Strong parity (do not touch):**
- Drawing tool set (rect/ellipse/diamond/line/arrow/freedraw/text + sticky)
- Selection/move/resize/rotate, group/ungroup, copy/paste in-app, undo/redo, delete
- Pan/zoom/dark-mode/infinite canvas
- Live cursors + selections + follow-me + named-user presence
- Local autosave (encrypted IndexedDB)
- PNG export, JSON export, hyperlinks, locks, laser, mobile pinch
- Pen pressure on freedraw, mermaid import, frames data model

**High-value gaps to close (small, in-scope):**
1. **Eraser tool** — enum already reserved; ~1 PR.
2. **Duplicate (Cmd+D), Flip H/V, Send-to-front/back, Layer-ordering UI** — all leverage existing element model.
3. **Align + Distribute** — multi-element ops; ~1 PR.
4. **Zoom-to-fit / zoom-to-selection** — viewport math + 2 toolbar buttons.
5. **Grid rendering + snap-to-grid + snap-to-objects** — visual grid + snap engine.
6. **System clipboard interop** — paste into web-clipboard; export `excalidraw/clipboard` MIME.
7. **JSON import (file picker)** — counterpart to existing export.
8. **View-mode / read-only share link** — gate inputs + URL `?mode=view`.
9. **Cross-tab IndexedDB coordination** — broadcast channel between tabs.
10. **Layer ordering UI** — model already has `zIndex`.

**Large gaps (separate epics):**
- **Excalidraw `.excalidrawlib` library + libraries.excalidraw.com interop** — drift toward Excalidraw's ecosystem. Worth doing only if the user community wants the catalog.
- **Lasso tool** — different selection paradigm.
- **Lossless JSON-in-PNG/SVG embed** — needs a chunk encoder/decoder.
- **Image crop editor + background-removal** — image-tool epic.
- **Charts (radar / multi-series)** — separate "Chart" element type.
- **Excalifont CJK font** — fontfile + license review.

**Excluded by policy:**
- All AI features (Magic Frame, wireframe-to-code, text-to-diagram, BYOK token UIs, MCP).

**Where Rapidly leads (don't lose):**
- Yjs CRDT instead of OT (better merge semantics for offline-first)
- E2EE on every Y update + Awareness frame (Excalidraw's E2EE only on Excalidraw+ paid tier)
- Self-hosted COTURN signaling (no third-party room server)
- Command palette (Cmd+K) over ~50 actions
- Keyboard-shortcut overlay UI
- Mermaid parser is in-tree (no separate package)
- Sticky-note element type (Excalidraw has none)

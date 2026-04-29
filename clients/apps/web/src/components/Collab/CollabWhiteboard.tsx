'use client'

/**
 * Collab v2 whiteboard — the production canvas renderer.
 *
 * Mounts with an optional external ``doc``/``presence``/``selfUser`` to
 * host inside a chamber session, or stand-alone (no props) as an
 * internal demo for ``/dev/collab-render``.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as Y from 'yjs'

import { align, distribute } from '@/utils/collab/align'
import { makeAlignmentGuidesOverlay } from '@/utils/collab/alignment-guides-overlay'
import { clearCanvas } from '@/utils/collab/clear-canvas'
import {
  copy as clipboardCopy,
  cut as clipboardCut,
  duplicate as clipboardDuplicate,
  paste as clipboardPaste,
  getClipboard,
  serialiseSelection,
} from '@/utils/collab/clipboard'
import { type Command } from '@/utils/collab/command-palette'
import { makeCursorOverlay } from '@/utils/collab/cursor-overlay'
import {
  createElementStore,
  type ElementStore,
} from '@/utils/collab/element-store'
import { EMBED_SANDBOX, isEmbeddableUrl } from '@/utils/collab/embed-allowlist'
import {
  computeBounds,
  downloadBlob,
  exportToJSON,
  exportToPNG,
} from '@/utils/collab/export'
import { flipHorizontal, flipVertical } from '@/utils/collab/flip'
import {
  createFollowMeController,
  type FollowMeController,
} from '@/utils/collab/follow-me'
import { expandToGroups, group, ungroup } from '@/utils/collab/groups'
import { hasLink, setLink } from '@/utils/collab/hyperlinks'
import {
  createImageElement,
  extractPastedImage,
} from '@/utils/collab/image-paste'
import {
  importScene,
  isImportError,
  parseExportedScene,
} from '@/utils/collab/import-json'
import {
  createInstallPromptController,
  type InstallPromptController,
} from '@/utils/collab/install-prompt'
import {
  ageToAlpha,
  createLaserState,
  type LaserController,
} from '@/utils/collab/laser'
import { makeLaserOverlay } from '@/utils/collab/laser-overlay'
import { filterUnlocked, toggleLock } from '@/utils/collab/locks'
import { mermaidToElements, parseMermaid } from '@/utils/collab/mermaid'
import { deltaFromArrowKey, nudge } from '@/utils/collab/nudge'
import {
  createPinchPanGesture,
  type PinchPanGesture,
} from '@/utils/collab/pinch-gesture'
import {
  createPointerPreference,
  HANDLE_SIZE_FOR_PRECISION,
  type PointerPrecision,
} from '@/utils/collab/pointer-preference'
import {
  inMemoryPresenceSource,
  type InMemoryPresenceSource,
  type PresenceSource,
  type PresenceUser,
} from '@/utils/collab/presence'
import {
  advanceFrame,
  computeFrames,
  viewportForBounds,
} from '@/utils/collab/presentation'
import { makeRemoteSelectionOverlay } from '@/utils/collab/remote-selection-overlay'
import { Renderer } from '@/utils/collab/renderer'
import { SelectionState } from '@/utils/collab/selection'
import { makeSelectionOverlay } from '@/utils/collab/selection-overlay'
import { exportToSVG } from '@/utils/collab/svg-export'
import {
  parseClipboardText,
  readSystemClipboardPayload,
  writeSystemClipboard,
} from '@/utils/collab/system-clipboard'
import { onEditRequest } from '@/utils/collab/text-editing'
import { toolIdForKey } from '@/utils/collab/tool-keys'
import {
  currentMarqueeRect,
  currentSnapGuides,
  hoverCursor,
  toolFor,
  type SelectToolCtx,
  type Tool,
  type ToolCtx,
  type ToolId,
} from '@/utils/collab/tools'
import { createUndoManager, type UndoController } from '@/utils/collab/undo'
import {
  isReadOnlyPaletteCommand,
  isReadOnlyTool,
  isViewModeShortcutAllowed,
  withViewModeUrl,
} from '@/utils/collab/view-mode'
import { makeViewport, zoomAt, type Viewport } from '@/utils/collab/viewport'
import { animateViewport } from '@/utils/collab/viewport-transitions'
import {
  bringForward,
  bringToFront,
  sendBackward,
  sendToBack,
} from '@/utils/collab/z-order'
import {
  viewportForKeyboardZoom,
  zoomDirectionForKey,
} from '@/utils/collab/zoom-keyboard'
import { zoomToFit, zoomToSelection } from '@/utils/collab/zoom-to-fit'

import { CommandPalette } from './Whiteboard/CommandPalette'
import { EmbedsOverlay } from './Whiteboard/EmbedsOverlay'
import { HyperlinkBadge } from './Whiteboard/HyperlinkBadge'
import { MobilePropertiesSheet } from './Whiteboard/MobilePropertiesSheet'
import { PropertiesPanel } from './Whiteboard/PropertiesPanel'
import { ServiceWorkerRegistrar } from './Whiteboard/ServiceWorkerRegistrar'
import { ShortcutsOverlay } from './Whiteboard/ShortcutsOverlay'
import { TextEditor } from './Whiteboard/TextEditor'

function seedScene(store: ElementStore): void {
  store.transact(() => {
    store.create({
      type: 'rect',
      x: 100,
      y: 100,
      width: 160,
      height: 80,
      roundness: 12,
      strokeColor: '#1e1e1e',
      fillColor: '#fde68a',
      fillStyle: 'solid',
    })
    store.create({
      type: 'ellipse',
      x: 300,
      y: 120,
      width: 140,
      height: 100,
      strokeColor: '#1e40af',
      fillColor: '#dbeafe',
      fillStyle: 'solid',
    })
  })
}

const TOOL_CHOICES: Array<{ id: ToolId; label: string; hint: string }> = [
  { id: 'hand', label: 'Hand', hint: 'Drag to pan' },
  {
    id: 'select',
    label: 'Select',
    hint: 'Click, drag-move, handle-resize, marquee — Delete to remove',
  },
  { id: 'rect', label: 'Rect', hint: 'Drag to draw a rectangle' },
  { id: 'ellipse', label: 'Ellipse', hint: 'Drag to draw an ellipse' },
  { id: 'diamond', label: 'Diamond', hint: 'Drag to draw a diamond' },
  { id: 'line', label: 'Line', hint: 'Drag; shift snaps to 45°' },
  { id: 'arrow', label: 'Arrow', hint: 'Drag; shift snaps to 45°' },
  { id: 'freedraw', label: 'Pen', hint: 'Freehand stroke with pressure' },
  {
    id: 'text',
    label: 'Text',
    hint: 'Click to add text — inline editor, Enter to commit',
  },
  {
    id: 'sticky',
    label: 'Sticky',
    hint: 'Click to add a sticky note; Enter commits',
  },
  {
    id: 'eraser',
    label: 'Eraser',
    hint: 'Drag over elements to delete them; release to commit',
  },
  { id: 'frame', label: 'Frame', hint: 'Drag to draw a labelled container' },
]

interface CollabWhiteboardProps {
  /** Optional externally-owned Y.Doc. When provided, the demo binds
   *  to it instead of creating its own — used by the chamber to host
   *  this component over a real ``useCollabRoom`` session. The caller
   *  owns the doc's lifecycle in that case; the demo will **not**
   *  destroy it on unmount. */
  doc?: Y.Doc
  /** Optional external presence source — when provided, overlays
   *  (cursor / remote-selection / laser) and the follow-me controller
   *  read from it instead of the built-in in-memory stub. The demo
   *  peer + self-laser simulators are hidden in this mode because
   *  they poke the *internal* source for visual-exercise purposes
   *  and would mix with real remote peers. */
  presence?: PresenceSource
  /** Local user identity to broadcast through ``presence.setLocal``.
   *  Required alongside ``presence`` for remote peers to see this
   *  user's cursor / selection; absent → read-only mode (peers show
   *  in this client, but this client is invisible to them). */
  selfUser?: PresenceUser
  /** When ``true``, the whiteboard renders in read-only mode: only
   *  pan/select tools, no keyboard mutations, no editing buttons.
   *  The caller (e.g. a "share view-only link" route) is responsible
   *  for setting this; the component itself doesn't infer it. */
  viewMode?: boolean
}

export function CollabWhiteboard({
  doc: externalDoc,
  presence: externalPresence,
  selfUser,
  viewMode = false,
}: CollabWhiteboardProps = {}) {
  const staticRef = useRef<HTMLCanvasElement | null>(null)
  const interactiveRef = useRef<HTMLCanvasElement | null>(null)
  const rendererRef = useRef<Renderer | null>(null)
  const storeRef = useRef<ElementStore | null>(null)
  const selectionRef = useRef<SelectionState>(new SelectionState())
  const activeToolRef = useRef<Tool | null>(null)
  const gestureToolRef = useRef<Tool | null>(null)
  const vpRef = useRef<Viewport>(makeViewport({ scrollX: -20, scrollY: -20 }))
  const presenceRef = useRef<InMemoryPresenceSource>(inMemoryPresenceSource())
  // The source overlays + follow-me actually read from. When an
  // external presence is provided, everything that *reads* points at
  // it; the internal in-memory ref stays available for the demo-peer
  // + self-laser simulators, which would otherwise pollute a real
  // session with their fake peers.
  const sourceRef = useRef<PresenceSource>(
    externalPresence ?? presenceRef.current,
  )
  sourceRef.current = externalPresence ?? presenceRef.current
  // Stable ref to the local user identity so pointer-move handlers
  // don't need the prop in their dep array (React re-runs on every
  // parent render otherwise).
  const selfUserRef = useRef<PresenceUser | undefined>(selfUser)
  selfUserRef.current = selfUser
  // Laser-active mirror so the self-paint pass reads the latest
  // value from inside the canvas interactive-paint closure without
  // capturing ``laserActive`` stale on first render.
  const laserActiveRef = useRef(false)

  /** Broadcast the current viewport through the external presence
   *  source so remote peers can follow the local user. Skipped when
   *  no external session is wired (standalone demo) or the local
   *  identity isn't known yet. Callers invoke this from the exact
   *  sites that mutate ``vpRef.current`` — wheel, pinch, presentation
   *  transition — but **not** from the follow-me apply path, which
   *  would create a mirror-a-peer feedback loop. */
  const publishViewport = useCallback(() => {
    if (!externalPresence || !selfUserRef.current) return
    const vp = vpRef.current
    externalPresence.setLocal({
      user: selfUserRef.current,
      viewport: {
        scale: vp.scale,
        scrollX: vp.scrollX,
        scrollY: vp.scrollY,
      },
    })
  }, [externalPresence])
  const demoPeerFrameRef = useRef<number | null>(null)
  const followControllerRef = useRef<FollowMeController | null>(null)
  const undoRef = useRef<UndoController | null>(null)
  const laserRef = useRef<LaserController | null>(null)
  const installRef = useRef<InstallPromptController | null>(null)
  const pinchRef = useRef<PinchPanGesture>(createPinchPanGesture())
  const precisionRef = useRef<PointerPrecision>('fine')

  // View mode keeps the tool to read-only choices via the toolbar +
  // palette filter and the keyboard whitelist (which drops the
  // r/o/d/l/a/p/t/s tool-letter hotkeys). The useEffect below flips
  // any sneaked-through editing tool back to hand for belt-and-braces.
  const [toolId, setToolId] = useState<ToolId>('hand')
  const [zoom, setZoom] = useState(1)
  const [elementCount, setElementCount] = useState(0)
  const [selectionSize, setSelectionSize] = useState(0)
  const [demoPeerActive, setDemoPeerActive] = useState(false)
  const [followingDemoPeer, setFollowingDemoPeer] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [laserActive, setLaserActive] = useState(false)
  const [presentationActive, setPresentationActive] = useState(false)
  const [presentationIndex, setPresentationIndex] = useState(0)
  const [canInstall, setCanInstall] = useState(false)
  const [mobileStyleOpen, setMobileStyleOpen] = useState(false)
  /** When the text tool fires an edit request (or the user double-
   *  clicks a text element), we mount the TextEditor overlay on
   *  this id. Null = no editor active. */
  const [editingId, setEditingId] = useState<string | null>(null)

  // Subscribe to text-edit requests from tools.
  useEffect(() => {
    return onEditRequest((id) => {
      setEditingId(id)
    })
  }, [])

  // PWA install prompt — Chromium fires the deferred prompt once per
  // page load. Controller captures it even if the user hasn't mounted
  // this component yet (it re-checks on subscribe).
  useEffect(() => {
    const ctrl = createInstallPromptController()
    installRef.current = ctrl
    setCanInstall(ctrl.canInstall())
    const off = ctrl.subscribe(() => setCanInstall(ctrl.canInstall()))
    return () => {
      off()
      ctrl.dispose()
      installRef.current = null
    }
  }, [])

  // Pointer precision — coarse (finger) grows handles + hit radius so
  // resize targets stay tappable on touch. Subscribes so a user
  // plugging in a mouse mid-session flips back to fine handles.
  useEffect(() => {
    const pref = createPointerPreference()
    precisionRef.current = pref.current()
    rendererRef.current?.invalidate()
    const off = pref.subscribe((next) => {
      precisionRef.current = next
      rendererRef.current?.invalidate()
    })
    return () => {
      off()
      pref.dispose()
    }
  }, [])

  // Demo-only: animate a fake remote cursor in a slow circle so
  // visitors can see the cursor overlay without a second browser tab.
  // Every few seconds it rotates its "selection" to a different
  // element so the remote-selection overlay can be exercised too.
  useEffect(() => {
    // With an external presence source the chamber has its own real
    // peers — injecting a fake ""Demo peer"" into the internal source
    // would confuse the UI (it wouldn't appear in overlays either,
    // since those read from the external source).
    if (externalPresence) return
    const source = presenceRef.current
    if (!demoPeerActive) {
      source.removeRemote(1)
      if (demoPeerFrameRef.current !== null) {
        cancelAnimationFrame(demoPeerFrameRef.current)
        demoPeerFrameRef.current = null
      }
      return
    }
    const start = performance.now()
    const step = (now: number): void => {
      const t = (now - start) / 1000
      const cx = 240 + Math.cos(t) * 140
      const cy = 180 + Math.sin(t) * 80
      const store = storeRef.current
      let selection: string[] = []
      if (store) {
        const ids = store.list().map((el) => el.id)
        if (ids.length > 0) {
          selection = [ids[Math.floor(t / 2) % ids.length]]
        }
      }
      source.pushRemote({
        clientId: 1,
        user: { id: 'demo-peer', color: '#2f9e44', name: 'Demo peer' },
        cursor: { x: cx, y: cy },
        selection,
        // Slowly drifting viewport so "Follow demo peer" is visibly
        // different from the static one the user set up.
        viewport: {
          scale: 1 + Math.sin(t * 0.2) * 0.15,
          scrollX: -40 + Math.cos(t * 0.3) * 80,
          scrollY: -40 + Math.sin(t * 0.3) * 40,
        },
      })
      demoPeerFrameRef.current = requestAnimationFrame(step)
    }
    demoPeerFrameRef.current = requestAnimationFrame(step)
    return () => {
      if (demoPeerFrameRef.current !== null) {
        cancelAnimationFrame(demoPeerFrameRef.current)
        demoPeerFrameRef.current = null
      }
    }
  }, [demoPeerActive, externalPresence])

  useEffect(() => {
    activeToolRef.current = toolFor(toolId)
  }, [toolId])

  // Entering view mode flips any editing tool back to hand. Leaving
  // view mode preserves whatever the user picked before — they may
  // want to resume drawing without a manual tool re-pick.
  useEffect(() => {
    if (viewMode && !isReadOnlyTool(toolId)) {
      setToolId('hand')
    }
  }, [viewMode, toolId])

  useEffect(() => {
    const s = staticRef.current
    const i = interactiveRef.current
    if (!s || !i) return

    // Bind to the caller's doc when provided, otherwise spin up our
    // own + seed the demo scene. Track whether we own it so the
    // cleanup branch doesn't destroy a doc the caller still needs.
    const ownsDoc = externalDoc === undefined
    const doc = externalDoc ?? new Y.Doc()
    const store = createElementStore(doc)
    if (ownsDoc) seedScene(store)
    storeRef.current = store
    setElementCount(store.size)

    const r = new Renderer({
      staticCanvas: s,
      interactiveCanvas: i,
      store,
      viewport: vpRef.current,
    })
    rendererRef.current = r

    const selection = selectionRef.current

    // Keep the selection pruned to live elements — a remote delete
    // that clobbers a selected element should drop it from our
    // selection too (matches §3.4 of the plan).
    const unobserveStore = store.observe(() => {
      setElementCount(store.size)
      const liveIds = new Set<string>()
      for (const el of store.list()) liveIds.add(el.id)
      selection.reconcile(liveIds)
    })

    const unsubscribeSelection = selection.subscribe((ids) => {
      setSelectionSize(ids.size)
      r.invalidate()
      // Broadcast the new selection through the external source so
      // remote peers' selection-overlay paints stay in sync.
      if (externalPresence && selfUserRef.current) {
        externalPresence.setLocal({
          user: selfUserRef.current,
          selection: Array.from(ids),
        })
      }
    })

    // Selection overlay paints the dashed bounding box + marquee;
    // cursor overlay paints remote peers' pointers. The two compose
    // trivially — each runs against the world-space transform.
    const selectionPaint = makeSelectionOverlay({
      store,
      selection,
      getMarquee: () => currentMarqueeRect(),
      getViewport: () => r.getViewport(),
      getHandleSizePx: () => HANDLE_SIZE_FOR_PRECISION[precisionRef.current],
    })
    // Overlays + follow-me read from the effective source (external
    // when supplied, internal otherwise). Wrapped in thin
    // pass-through sources so a prop flip mid-mount is picked up on
    // the next paint without a renderer tear-down.
    const effectiveSource: PresenceSource = {
      getRemotes: () => sourceRef.current.getRemotes(),
      subscribe: (fn) => sourceRef.current.subscribe(fn),
      setLocal: (state) => sourceRef.current.setLocal(state),
    }
    const cursorPaint = makeCursorOverlay({
      source: effectiveSource,
      getViewport: () => r.getViewport(),
    })
    const remoteSelectionPaint = makeRemoteSelectionOverlay({
      store,
      source: effectiveSource,
      getViewport: () => r.getViewport(),
    })
    const laserPaint = makeLaserOverlay({
      source: effectiveSource,
      getViewport: () => r.getViewport(),
    })
    const alignmentGuidesPaint = makeAlignmentGuidesOverlay({
      getGuides: () => currentSnapGuides(),
      getViewport: () => r.getViewport(),
    })
    // Self-laser paint pass for chamber mode: the external source's
    // ``getRemotes`` excludes the local client, so without this the
    // user can't see their own laser trail even while peers do. On
    // the standalone demo page the internal source's fake self-peer
    // already covers this, so we only paint when external presence
    // is wired AND laser is active.
    const selfLaserPaint = (ctx: CanvasRenderingContext2D): void => {
      if (!externalPresence || !laserActiveRef.current) return
      const laser = laserRef.current
      if (!laser) return
      const snap = laser.snapshot(performance.now())
      if (snap.points.length === 0) return
      const color = selfUserRef.current?.color ?? '#ef4444'
      // Inline painter matches ``makeLaserOverlay``'s curve but
      // scales line width / head radius through the viewport so zoom
      // keeps it screen-constant.
      const vp = r.getViewport()
      const s = 1 / vp.scale
      let newestT = -Infinity
      for (const p of snap.points) if (p.t > newestT) newestT = p.t
      ctx.save()
      ctx.strokeStyle = color
      ctx.lineWidth = 4 * s
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      for (let i = 1; i < snap.points.length; i++) {
        const a = snap.points[i - 1]
        const b = snap.points[i]
        ctx.globalAlpha = ageToAlpha(newestT - a.t)
        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        ctx.stroke()
      }
      const head = snap.points[snap.points.length - 1]
      ctx.globalAlpha = 1
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.arc(head.x, head.y, 6 * s, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()
    }
    r.setInteractivePaint((ctx) => {
      // Paint order: remote selections sit below the local dashed
      // overlay; laser trails layer above selections but below cursors
      // so the pointer itself stays crisp on top; cursors sit above
      // everything.
      remoteSelectionPaint(ctx)
      selectionPaint(ctx)
      alignmentGuidesPaint(ctx)
      laserPaint(ctx)
      selfLaserPaint(ctx)
      cursorPaint(ctx)
    })

    // Re-paint whenever a remote cursor updates.
    const unsubscribePresence = effectiveSource.subscribe(() => {
      r.invalidate()
    })

    // Follow-me controller writes the target peer's viewport into
    // our live viewport object and repaints. Calling ``setTarget``
    // from the UI below activates it; ``null`` tears it off.
    const follow = createFollowMeController({
      source: effectiveSource,
      apply: (vp) => {
        const live = vpRef.current
        live.scale = vp.scale
        live.scrollX = vp.scrollX
        live.scrollY = vp.scrollY
        r.setViewport(live)
        setZoom(Math.round(vp.scale * 100) / 100)
      },
    })
    followControllerRef.current = follow

    // Undo / redo — scoped to local-origin transactions via
    // ORIGIN_LOCAL, so remote peers' edits never get rewound.
    undoRef.current = createUndoManager(store)

    // Laser pointer state — sliding window of recent cursor samples.
    // Broadcast through the presence source when laser mode is on.
    laserRef.current = createLaserState()

    const onResize = () => r.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      unobserveStore()
      unsubscribeSelection()
      unsubscribePresence()
      follow.dispose()
      followControllerRef.current = null
      undoRef.current?.dispose()
      undoRef.current = null
      laserRef.current = null
      r.destroy()
      rendererRef.current = null
      storeRef.current = null
      // Only destroy the doc when we own it — externally-provided
      // docs outlive this component and get cleaned up by the caller
      // (e.g. useCollabRoom's leave).
      if (ownsDoc) doc.destroy()
    }
    // ownsDoc captured at effect start; re-running the effect on
    // prop change would force a full store rebuild, which the caller
    // almost never wants.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Toggle follow-me on / off when the checkbox flips.
  useEffect(() => {
    const ctrl = followControllerRef.current
    if (!ctrl) return
    ctrl.setTarget(followingDemoPeer ? 1 : null)
  }, [followingDemoPeer])

  // Presentation mode: ease the viewport to the current frame. A
  // rapid key-mash cancels the previous animation so the camera lerps
  // from wherever it is now rather than queuing up.
  useEffect(() => {
    if (!presentationActive) return
    const renderer = rendererRef.current
    const store = storeRef.current
    const canvas = interactiveRef.current
    if (!renderer || !store || !canvas) return
    const frames = computeFrames(store.list())
    if (frames.length === 0) return
    const index = Math.min(presentationIndex, frames.length - 1)
    const rect = canvas.getBoundingClientRect()
    const target = viewportForBounds(
      frames[index].bounds,
      rect.width,
      rect.height,
    )
    const handle = animateViewport({ ...vpRef.current }, target, {
      durationMs: 400,
      onFrame: (vp) => {
        vpRef.current.scale = vp.scale
        vpRef.current.scrollX = vp.scrollX
        vpRef.current.scrollY = vp.scrollY
        renderer.setViewport(vpRef.current)
        setZoom(Math.round(vp.scale * 100) / 100)
        // Broadcast through external presence so a ""follow me""
        // audience in another tab moves in sync with the presenter.
        publishViewport()
      },
    })
    return () => handle.cancel()
  }, [presentationActive, presentationIndex, publishViewport])

  // Laser mode: prune the trail on every RAF while active so the
  // tail fades away even when the user stops moving. Publishes
  // through the external presence when wired (so remote peers see
  // the trail) and falls back to a self-push into the internal
  // source on the standalone demo page (so the overlay reflects the
  // simulator without a peer to bounce off).
  useEffect(() => {
    laserActiveRef.current = laserActive
    if (!laserActive) {
      laserRef.current?.clear()
      if (externalPresence && selfUserRef.current) {
        // Clear the laser field on the external source so peers drop
        // the trail. Keep user / cursor fields omitted — next
        // pointer-move will repopulate them.
        externalPresence.setLocal({ user: selfUserRef.current })
      } else {
        presenceRef.current.removeRemote(999)
      }
      rendererRef.current?.invalidate()
      return
    }
    let handle = 0
    const tick = (): void => {
      const laser = laserRef.current
      const renderer = rendererRef.current
      if (laser && renderer) {
        const snap = laser.snapshot(performance.now())
        if (externalPresence && selfUserRef.current) {
          // Chamber mode: ride on the real presence source. Remote
          // peers' ``laser-overlay`` reads it; our own view picks up
          // the trail via the self-paint pass below.
          externalPresence.setLocal({
            user: selfUserRef.current,
            laser: snap,
          })
        } else if (snap.points.length > 0) {
          const head = snap.points[snap.points.length - 1]
          presenceRef.current.pushRemote({
            clientId: 999,
            user: {
              id: 'self-laser',
              color: '#ef4444',
              name: 'You (laser)',
            },
            cursor: { x: head.x, y: head.y },
            laser: snap,
          })
        } else {
          presenceRef.current.removeRemote(999)
        }
        renderer.invalidate()
      }
      handle = requestAnimationFrame(tick)
    }
    handle = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(handle)
    }
  }, [laserActive, externalPresence])

  // Global paste listener for image-on-clipboard → image element.
  // Non-image pastes fall through to the existing Cmd+V keydown
  // handler (in-app clipboard) so both flows keep their contract.
  useEffect(() => {
    const onPaste = async (e: ClipboardEvent): Promise<void> => {
      const target = e.target as HTMLElement | null
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return
      }
      const store = storeRef.current
      const renderer = rendererRef.current
      if (!store || !renderer) return
      // Try our JSON envelope first — pasting from another Rapidly tab
      // ships a Rapidly payload as text. This is the cross-tab path
      // the keyboard handler also takes; we duplicate the lookup here
      // so a paste *event* (e.g. from the system menu) is handled
      // without needing keyboard focus.
      const text = e.clipboardData?.getData('text/plain') ?? ''
      const ourPayload = parseClipboardText(text)
      if (ourPayload) {
        e.preventDefault()
        const newIds = clipboardPaste(store, ourPayload)
        if (newIds.length > 0) selectionRef.current.set(newIds)
        return
      }
      const image = await extractPastedImage(e.clipboardData)
      if (!image) return
      e.preventDefault()
      // Drop the image at the current viewport centre.
      const canvas = interactiveRef.current
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const center = renderer.screenToWorld(rect.width / 2, rect.height / 2)
      const id = createImageElement(store, image, { center })
      selectionRef.current.set([id])
    }
    document.addEventListener('paste', onPaste)
    return () => {
      document.removeEventListener('paste', onPaste)
    }
  }, [])

  const toolCtx = useCallback((): ToolCtx | null => {
    const renderer = rendererRef.current
    const store = storeRef.current
    if (!renderer || !store) return null
    const base: SelectToolCtx = {
      store,
      renderer,
      viewport: renderer.getViewport(),
      screenToWorld: (x, y) => renderer.screenToWorld(x, y),
      invalidate: () => renderer.invalidate(),
      selection: selectionRef.current,
      getHitRadiusPx: () =>
        // Hit radius matches the visual handle so the tap target
        // lines up with what the user sees.
        HANDLE_SIZE_FOR_PRECISION[precisionRef.current] / 2 + 4,
    }
    return base
  }, [])

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      const canvas = interactiveRef.current
      const tool = activeToolRef.current
      const ctx = toolCtx()
      if (!canvas || !tool || !ctx) return
      // Cmd/Ctrl-click on an element with a hyperlink opens it in a
      // new tab and short-circuits the tool gesture. Plan §2 calls
      // this out: ""Cmd+click opens in new tab"". The new tab gets
      // ``noopener,noreferrer`` so it can't reach back into our window.
      if (e.metaKey || e.ctrlKey) {
        const renderer = rendererRef.current
        const store = storeRef.current
        if (renderer && store) {
          const rect = canvas.getBoundingClientRect()
          const world = renderer.screenToWorld(
            e.clientX - rect.left,
            e.clientY - rect.top,
          )
          const hitId = renderer.hitTest(world.x, world.y)
          if (hitId) {
            const el = store.get(hitId)
            if (el && hasLink(el) && el.link) {
              e.preventDefault()
              window.open(el.link, '_blank', 'noopener,noreferrer')
              return
            }
          }
        }
      }
      // Route touch / pen pointers through the pinch gesture so two-
      // finger pinch + pan always works regardless of active tool.
      // Mouse pointers bypass — they never multi-touch.
      if (e.pointerType === 'touch' || e.pointerType === 'pen') {
        const rect = canvas.getBoundingClientRect()
        pinchRef.current.onPointerDown({
          id: e.pointerId,
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
        })
        if (pinchRef.current.active()) {
          // Pinch took over — cancel any in-progress single-finger
          // gesture so a stray tap doesn't leave a half-drawn shape.
          if (gestureToolRef.current) {
            gestureToolRef.current.onCancel?.(ctx)
            gestureToolRef.current = null
          }
          canvas.setPointerCapture(e.pointerId)
          return
        }
      }
      canvas.setPointerCapture(e.pointerId)
      gestureToolRef.current = tool
      tool.onPointerDown(ctx, e.nativeEvent)
    },
    [toolCtx],
  )

  const [hoverCursorStyle, setHoverCursorStyle] = useState<string | null>(null)

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      const canvas = interactiveRef.current
      const renderer = rendererRef.current
      // Two-finger pinch + pan — runs before everything else so
      // pointer moves during a pinch don't leak into tools.
      if (
        (e.pointerType === 'touch' || e.pointerType === 'pen') &&
        canvas &&
        renderer
      ) {
        const rect = canvas.getBoundingClientRect()
        const update = pinchRef.current.onPointerMove({
          id: e.pointerId,
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
        })
        if (update) {
          // Apply scale around the pinch centre, then pan by the
          // midpoint delta in world units.
          const vp = renderer.getViewport()
          const scaled = zoomAt(
            vp,
            update.centerScreenX,
            update.centerScreenY,
            vp.scale * update.scaleFactor,
          )
          scaled.scrollX -= update.panDeltaScreenX / scaled.scale
          scaled.scrollY -= update.panDeltaScreenY / scaled.scale
          vpRef.current = scaled
          renderer.setViewport(scaled)
          setZoom(Math.round(scaled.scale * 100) / 100)
          publishViewport()
          return
        }
      }
      // Laser pointer: regardless of the active tool, push the
      // current world coord into the trail + broadcast via presence.
      // Runs on every pointer move (including hover-only moves).
      if (laserActive && renderer && laserRef.current && canvas) {
        const rect = canvas.getBoundingClientRect()
        const world = renderer.screenToWorld(
          e.clientX - rect.left,
          e.clientY - rect.top,
        )
        const trail = laserRef.current.push(world.x, world.y, performance.now())
        presenceRef.current.pushRemote({
          clientId: 999,
          user: { id: 'self-laser', color: '#ef4444', name: 'You (laser)' },
          cursor: { x: world.x, y: world.y },
          laser: trail,
        })
      }
      // Local broadcast — when an external presence + self identity
      // are wired, publish the current cursor through the shared
      // source so remote peers see it. Uses world coords (same as
      // Phase 11 ``cursor-overlay``) so peers reproject to their
      // own viewport.
      if (
        externalPresence &&
        selfUserRef.current &&
        renderer &&
        canvas &&
        selectionRef.current
      ) {
        const rect = canvas.getBoundingClientRect()
        const world = renderer.screenToWorld(
          e.clientX - rect.left,
          e.clientY - rect.top,
        )
        externalPresence.setLocal({
          user: selfUserRef.current,
          cursor: { x: world.x, y: world.y },
          selection: Array.from(selectionRef.current.snapshot),
        })
      }
      const tool = gestureToolRef.current
      const ctx = toolCtx()
      if (!tool || !ctx) {
        // No active gesture — if the select tool is active, see whether
        // the cursor sits over a handle so we can swap its cursor.
        if (canvas && toolId === 'select' && ctx === null) {
          setHoverCursorStyle(null)
        }
        if (toolId === 'select' && canvas) {
          const active = toolCtx()
          if (active) {
            const rect = canvas.getBoundingClientRect()
            const next = hoverCursor(
              active as SelectToolCtx,
              e.clientX - rect.left,
              e.clientY - rect.top,
              active.renderer
                ? (activeToolRef.current?.cursor ?? 'default')
                : 'default',
            )
            setHoverCursorStyle(next)
          }
        }
        return
      }
      tool.onPointerMove(ctx, e.nativeEvent)
    },
    [toolCtx, toolId, laserActive, externalPresence, publishViewport],
  )

  const onPointerUp = useCallback(
    (e: React.PointerEvent) => {
      const canvas = interactiveRef.current
      // Touch / pen pointers always leave the pinch gesture whether
      // or not it was active, so a dropped finger can't linger in the
      // tracker and interfere with the next gesture.
      if (e.pointerType === 'touch' || e.pointerType === 'pen') {
        pinchRef.current.onPointerUp(e.pointerId)
      }
      const tool = gestureToolRef.current
      const ctx = toolCtx()
      gestureToolRef.current = null
      if (canvas && canvas.hasPointerCapture(e.pointerId)) {
        canvas.releasePointerCapture(e.pointerId)
      }
      if (!tool || !ctx) return
      tool.onPointerUp(ctx, e.nativeEvent)
      setZoom(Math.round(rendererRef.current!.getViewport().scale * 100) / 100)
    },
    [toolCtx],
  )

  const onDoubleClick = useCallback((e: React.MouseEvent) => {
    const canvas = interactiveRef.current
    const renderer = rendererRef.current
    const store = storeRef.current
    if (!canvas || !renderer || !store) return
    const rect = canvas.getBoundingClientRect()
    const world = renderer.screenToWorld(
      e.clientX - rect.left,
      e.clientY - rect.top,
    )
    const hitId = renderer.hitTest(world.x, world.y)
    if (!hitId) return
    const el = store.get(hitId)
    if (el?.type === 'text') {
      setEditingId(hitId)
    }
  }, [])

  const onDragOver = useCallback((e: React.DragEvent) => {
    // Required so the drop event fires. ``copy`` matches the cursor
    // most OSes show when dragging an image into a content area.
    if (e.dataTransfer?.types.includes('Files')) {
      e.preventDefault()
      e.dataTransfer.dropEffect = 'copy'
    }
  }, [])

  const onDrop = useCallback(async (e: React.DragEvent) => {
    if (!e.dataTransfer?.types.includes('Files')) return
    const canvas = interactiveRef.current
    const store = storeRef.current
    const renderer = rendererRef.current
    if (!canvas || !store || !renderer) return
    const rect = canvas.getBoundingClientRect()
    const cursorWorld = renderer.screenToWorld(
      e.clientX - rect.left,
      e.clientY - rect.top,
    )

    // Try JSON files first — they re Rapidly scene exports. Image
    // extraction silently skips non-image files so the JSON branch
    // doesn t accidentally swallow a real image.
    const file = e.dataTransfer.files?.[0]
    if (
      file &&
      (file.type === 'application/json' ||
        file.name.toLowerCase().endsWith('.json'))
    ) {
      e.preventDefault()
      let text: string
      try {
        text = await file.text()
      } catch {
        return
      }
      const parsed = parseExportedScene(text)
      if (isImportError(parsed)) {
        window.alert(
          'Could not import — file is not a Rapidly Collab JSON ' +
            `export (${parsed.reason}).`,
        )
        return
      }
      // Centre the import on the drop position rather than the
      // viewport, so the user's drop-target lands where they expect.
      const bounds = computeBounds(parsed.elements)
      const offset = bounds
        ? {
            x: cursorWorld.x - bounds.x - bounds.width / 2,
            y: cursorWorld.y - bounds.y - bounds.height / 2,
          }
        : { x: 0, y: 0 }
      const ids = importScene(store, parsed, { offset })
      if (ids.length > 0) selectionRef.current.set(ids)
      return
    }

    const image = await extractPastedImage(e.dataTransfer)
    if (!image) return
    e.preventDefault()
    // Drop the image at the actual cursor world position so the
    // user's drag-target lands where they expect — Excalidraw + Figma
    // both behave this way.
    const id = createImageElement(store, image, { center: cursorWorld })
    selectionRef.current.set([id])
  }, [])

  const onWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault()
      const canvas = interactiveRef.current
      const renderer = rendererRef.current
      if (!canvas || !renderer) return
      // Manual zoom breaks follow-me — otherwise the peer's next
      // awareness frame would yank the camera back and the user would
      // be fighting the follower.
      if (followControllerRef.current?.current() !== null) {
        followControllerRef.current?.setTarget(null)
        setFollowingDemoPeer(false)
      }
      const rect = canvas.getBoundingClientRect()
      const cx = e.clientX - rect.left
      const cy = e.clientY - rect.top
      const factor = Math.exp(-e.deltaY * 0.001)
      const next = zoomAt(
        renderer.getViewport(),
        cx,
        cy,
        renderer.getViewport().scale * factor,
      )
      vpRef.current = next
      renderer.setViewport(next)
      setZoom(Math.round(next.scale * 100) / 100)
      publishViewport()
    },
    [publishViewport],
  )

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      // View-mode gate: drop every shortcut not on the read-only
      // whitelist before any handler below has a chance to mutate.
      if (viewMode && !isViewModeShortcutAllowed(e)) {
        return
      }
      // Presentation mode: Arrow keys / Space advance the frame,
      // Shift+Arrow / Backspace / ArrowLeft rewind, Esc exits. Takes
      // precedence over every other binding while active.
      if (presentationActive) {
        if (e.key === 'Escape') {
          e.preventDefault()
          setPresentationActive(false)
          return
        }
        if (
          e.key === 'ArrowRight' ||
          e.key === 'ArrowDown' ||
          e.key === ' ' ||
          e.key === 'PageDown'
        ) {
          e.preventDefault()
          const store = storeRef.current
          if (!store) return
          const total = computeFrames(store.list()).length
          setPresentationIndex((i) => advanceFrame(i, total, 1))
          return
        }
        if (
          e.key === 'ArrowLeft' ||
          e.key === 'ArrowUp' ||
          e.key === 'PageUp' ||
          e.key === 'Backspace'
        ) {
          e.preventDefault()
          const store = storeRef.current
          if (!store) return
          const total = computeFrames(store.list()).length
          setPresentationIndex((i) => advanceFrame(i, total, -1))
          return
        }
        // Swallow other keys while presenting so the user can't
        // accidentally trigger a tool / undo during a talk.
        if (e.key !== 'F11') e.preventDefault()
        return
      }
      // Arrow-key nudge — moves the selection by 1 world unit (10 with
      // shift). Skipped when meta/ctrl is held (let zoom / browser
      // shortcuts pass) and when focus is inside a form input so the
      // text editor's caret keys still work.
      if (!e.metaKey && !e.ctrlKey) {
        const target = e.target as HTMLElement | null
        const inForm =
          !!target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        const delta = inForm ? null : deltaFromArrowKey(e.key, e.shiftKey)
        if (delta) {
          const store = storeRef.current
          const selection = selectionRef.current
          if (store && selection.size > 0) {
            e.preventDefault()
            nudge(store, selection.snapshot, delta.dx, delta.dy)
            return
          }
        }
      }
      // Single-letter tool-activation shortcuts (H / V / R / O / D /
      // L / A / P / T / S). Skipped when any modifier is pressed so
      // the Cmd+D etc. bindings below still work, and when focus is
      // inside a form input so typing ""r"" in the text editor is
      // unaffected.
      {
        const nextTool = toolIdForKey(e)
        if (nextTool) {
          e.preventDefault()
          setToolId(nextTool)
          return
        }
      }
      // Cmd/Ctrl+= zoom in, Cmd/Ctrl+- zoom out, Cmd/Ctrl+0 reset.
      // Anchored on the canvas mid-point so the visible-region centre
      // stays put. Skipped in form inputs so cmd+0 / cmd+= in a text
      // editor still does whatever the editor expects.
      if (e.metaKey || e.ctrlKey) {
        const target = e.target as HTMLElement | null
        const inForm =
          !!target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        const direction = inForm ? null : zoomDirectionForKey(e.key)
        if (direction) {
          const renderer = rendererRef.current
          const canvas = interactiveRef.current
          if (renderer && canvas) {
            e.preventDefault()
            const rect = canvas.getBoundingClientRect()
            const next = viewportForKeyboardZoom(
              renderer.getViewport(),
              direction,
              rect.width,
              rect.height,
            )
            vpRef.current = next
            renderer.setViewport(next)
            setZoom(Math.round(next.scale * 100) / 100)
            publishViewport()
            return
          }
        }
      }
      if (
        (e.metaKey || e.ctrlKey) &&
        e.shiftKey &&
        (e.key === 'p' || e.key === 'P')
      ) {
        // Cmd/Ctrl+Shift+P → open the command palette.
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        ) {
          return
        }
        e.preventDefault()
        setPaletteOpen(true)
        return
      }
      if (e.key === '?' && !e.metaKey && !e.ctrlKey) {
        // Shift+/ on US layouts. Skip when the pointer is inside a
        // form input so typing "?" in the text editor works normally.
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        ) {
          return
        }
        e.preventDefault()
        setShortcutsOpen(true)
        return
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const store = storeRef.current
        const selection = selectionRef.current
        if (!store || selection.size === 0) return
        // Avoid deleting form input fields elsewhere on the page —
        // our demo doesn't have any, but robust defence.
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' || target.isContentEditable)
        ) {
          return
        }
        e.preventDefault()
        // Skip locked elements — delete only those the user has
        // explicitly unlocked. Selection drops the deleted ids, keeps
        // the locked ones still selected so the user sees what stayed.
        const deletable = filterUnlocked(store, selection.snapshot)
        if (deletable.size === 0) return
        store.deleteMany(Array.from(deletable))
        const survivors = new Set(selection.snapshot)
        for (const id of deletable) survivors.delete(id)
        selection.set(survivors)
      } else if (e.key === 'Escape') {
        const tool = gestureToolRef.current
        const ctx = toolCtx()
        if (tool && ctx) tool.onCancel?.(ctx)
        gestureToolRef.current = null
        selectionRef.current.clear()
      } else if ((e.metaKey || e.ctrlKey) && (e.key === ']' || e.key === '[')) {
        // Cmd/Ctrl+] / [ → z-order controls. Shift modifier jumps
        // to front / back; plain is forward / backward one step.
        const store = storeRef.current
        const selection = selectionRef.current
        if (!store || selection.size === 0) return
        e.preventDefault()
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        ) {
          return
        }
        if (e.key === ']') {
          if (e.shiftKey) bringToFront(store, selection.snapshot)
          else bringForward(store, selection.snapshot)
        } else {
          if (e.shiftKey) sendToBack(store, selection.snapshot)
          else sendBackward(store, selection.snapshot)
        }
      } else if (
        (e.metaKey || e.ctrlKey) &&
        (e.key === 'c' ||
          e.key === 'v' ||
          e.key === 'x' ||
          e.key === 'd' ||
          e.key === 'C' ||
          e.key === 'V' ||
          e.key === 'X' ||
          e.key === 'D')
      ) {
        // Cmd/Ctrl+C / V / X / D → clipboard ops. Skip when typing in
        // a form input so the native browser copy/paste still works.
        const store = storeRef.current
        const selection = selectionRef.current
        if (!store) return
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        ) {
          return
        }
        const key = e.key.toLowerCase()
        if (key === 'c') {
          if (selection.size === 0) return
          e.preventDefault()
          clipboardCopy(store, selection.snapshot)
          // Mirror to the system clipboard so a paste in another tab
          // (or another browser window) picks up the same payload.
          // Fire-and-forget — the in-app buffer is the source of truth
          // and any error is swallowed by ``writeSystemClipboard``.
          const payload = serialiseSelection(store, selection.snapshot)
          if (payload) void writeSystemClipboard(payload)
        } else if (key === 'x') {
          if (selection.size === 0) return
          e.preventDefault()
          const payload = serialiseSelection(store, selection.snapshot)
          clipboardCut(store, selection.snapshot)
          selection.clear()
          if (payload) void writeSystemClipboard(payload)
        } else if (key === 'v') {
          e.preventDefault()
          // Prefer the system clipboard so cross-tab paste works; fall
          // back to the in-app buffer when the system clipboard isn't
          // ours (or isn't readable). Async branch — the in-app branch
          // runs synchronously below if the await yields null.
          ;(async () => {
            const remote = await readSystemClipboardPayload()
            const payload = remote ?? getClipboard()
            if (!payload) return
            const newIds = clipboardPaste(store, payload)
            if (newIds.length > 0) selection.set(newIds)
          })()
        } else if (key === 'd') {
          if (selection.size === 0) return
          e.preventDefault()
          const newIds = clipboardDuplicate(store, selection.snapshot)
          if (newIds.length > 0) selection.set(newIds)
        }
      } else if (
        (e.metaKey || e.ctrlKey) &&
        e.shiftKey &&
        (e.key === 'l' || e.key === 'L')
      ) {
        // Cmd/Ctrl+Shift+L → toggle lock on selection.
        const store = storeRef.current
        const selection = selectionRef.current
        if (!store || selection.size === 0) return
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        ) {
          return
        }
        e.preventDefault()
        toggleLock(store, selection.snapshot)
      } else if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        // Cmd/Ctrl+K → prompt for a URL and attach it to the selection.
        const store = storeRef.current
        const selection = selectionRef.current
        if (!store || selection.size === 0) return
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        ) {
          return
        }
        e.preventDefault()
        const [firstId] = selection.snapshot
        const existing = firstId ? (store.get(firstId)?.link ?? '') : ''
        const input = window.prompt('Link URL (empty to clear):', existing)
        if (input === null) return
        setLink(store, selection.snapshot, input)
      } else if (
        (e.metaKey || e.ctrlKey) &&
        (e.key === 'z' || e.key === 'Z' || e.key === 'y' || e.key === 'Y')
      ) {
        // Cmd/Ctrl+Z → undo. Shift+Z or Cmd+Y → redo.
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        ) {
          return
        }
        const undo = undoRef.current
        if (!undo) return
        e.preventDefault()
        const isRedo = e.key === 'y' || e.key === 'Y' || e.shiftKey
        if (isRedo) undo.redo()
        else undo.undo()
      } else if ((e.metaKey || e.ctrlKey) && (e.key === 'a' || e.key === 'A')) {
        // Cmd/Ctrl+A → select every (unlocked) element. Shift+Cmd+A
        // clears selection — matches Excalidraw + Figma. Skipped when
        // typing into a form input so the native browser select-all
        // still works there.
        const store = storeRef.current
        const selection = selectionRef.current
        if (!store) return
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        ) {
          return
        }
        e.preventDefault()
        if (e.shiftKey) {
          selection.clear()
        } else {
          // Locked elements are skipped — selecting them would invite
          // accidental Delete / drag attempts the lock then has to
          // refuse silently. Excalidraw matches.
          const ids = filterUnlocked(
            store,
            new Set(store.list().map((el) => el.id)),
          )
          selection.set(ids)
        }
      } else if ((e.metaKey || e.ctrlKey) && (e.key === 'g' || e.key === 'G')) {
        // Cmd/Ctrl+G → group. Cmd/Ctrl+Shift+G → ungroup.
        // Swallow the browser default (View > Find Next on some
        // browsers) and the inline-edit case — typing G in a textarea
        // must not group anything.
        const store = storeRef.current
        const selection = selectionRef.current
        if (!store || selection.size === 0) return
        const target = e.target as HTMLElement | null
        if (
          target &&
          (target.tagName === 'INPUT' ||
            target.tagName === 'TEXTAREA' ||
            target.isContentEditable)
        ) {
          return
        }
        e.preventDefault()
        if (e.shiftKey) {
          ungroup(store, selection.snapshot)
        } else {
          const newGroup = group(store, selection.snapshot)
          // After grouping, expand the selection to the whole group so
          // any subsequent action (drag, style, layer) treats it as a
          // unit. With the new group id on every selected element, the
          // expansion is effectively a no-op but keeps semantics
          // explicit for readers.
          if (newGroup) {
            selection.set(expandToGroups(store, selection.snapshot))
          }
        }
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [toolCtx, presentationActive, viewMode, publishViewport])

  const activeChoice = TOOL_CHOICES.find((t) => t.id === toolId)

  // Command palette entries. Re-derives when the selection / tool
  // context changes so the commands close over fresh refs; the palette
  // itself takes this as a prop and re-filters on every open.
  const commands = useMemo<Command[]>(() => {
    const list: Command[] = []
    // Tool activation.
    for (const t of TOOL_CHOICES) {
      list.push({
        id: `tool.${t.id}`,
        label: `${t.label} tool`,
        category: 'Tool',
        keywords: [t.id, 'tool'],
        run: () => setToolId(t.id),
      })
    }
    // Export actions.
    list.push({
      id: 'export.png',
      label: 'Export PNG',
      category: 'Export',
      shortcut: [],
      run: async () => {
        const store = storeRef.current
        if (!store) return
        const blob = await exportToPNG(store.list())
        if (blob) downloadBlob(blob, 'rapidly-collab.png')
      },
    })
    list.push({
      id: 'export.json',
      label: 'Export JSON',
      category: 'Export',
      run: () => {
        const store = storeRef.current
        if (!store) return
        const blob = new Blob(
          [JSON.stringify(exportToJSON(store.list()), null, 2)],
          { type: 'application/json' },
        )
        downloadBlob(blob, 'rapidly-collab.json')
      },
    })
    list.push({
      id: 'export.svg',
      label: 'Export SVG',
      category: 'Export',
      run: () => {
        const store = storeRef.current
        if (!store) return
        const svg = exportToSVG(store.list())
        const blob = new Blob([svg], { type: 'image/svg+xml' })
        downloadBlob(blob, 'rapidly-collab.svg')
      },
    })
    // Editing.
    list.push({
      id: 'edit.undo',
      label: 'Undo',
      category: 'Edit',
      shortcut: ['Mod', 'Z'],
      run: () => {
        undoRef.current?.undo()
      },
    })
    list.push({
      id: 'edit.redo',
      label: 'Redo',
      category: 'Edit',
      shortcut: ['Mod', 'Shift', 'Z'],
      run: () => {
        undoRef.current?.redo()
      },
    })
    list.push({
      id: 'edit.selectAll',
      label: 'Select all',
      category: 'Edit',
      shortcut: ['Mod', 'A'],
      keywords: ['select', 'all', 'everything'],
      run: () => {
        const store = storeRef.current
        if (!store) return
        const ids = filterUnlocked(
          store,
          new Set(store.list().map((el) => el.id)),
        )
        selectionRef.current.set(ids)
      },
    })
    list.push({
      id: 'edit.clearSelection',
      label: 'Clear selection',
      category: 'Edit',
      shortcut: ['Mod', 'Shift', 'A'],
      keywords: ['deselect', 'clear', 'none'],
      run: () => {
        selectionRef.current.clear()
      },
    })
    list.push({
      id: 'edit.clearCanvas',
      label: 'Clear canvas…',
      category: 'Edit',
      keywords: ['clear', 'wipe', 'reset', 'empty', 'delete all'],
      run: () => {
        const store = storeRef.current
        if (!store) return
        if (store.size === 0) return
        // Confirmation gate — clear-canvas is undoable but a remote
        // peer reads it instantly; we don t want to wipe a shared
        // session by accident. Native ``confirm`` is the cheapest
        // appropriate UX.
        const ok = window.confirm(
          `Clear all ${store.size} element${
            store.size === 1 ? '' : 's'
          } from the canvas? This can be undone with Cmd+Z.`,
        )
        if (!ok) return
        clearCanvas(store)
        selectionRef.current.clear()
      },
    })
    list.push({
      id: 'edit.resetRotation',
      label: 'Reset rotation',
      category: 'Edit',
      keywords: ['rotation', 'angle', 'reset', 'unrotate', '0°'],
      run: () => {
        const store = storeRef.current
        if (!store) return
        const ids = Array.from(selectionRef.current.snapshot)
        if (ids.length === 0) return
        const patches = ids
          .map((id) => store.get(id))
          .filter(
            (el): el is NonNullable<typeof el> =>
              el !== null && !el.locked && el.angle !== 0,
          )
          .map((el) => ({ id: el.id, patch: { angle: 0 } }))
        if (patches.length > 0) store.updateMany(patches)
      },
    })
    list.push({
      id: 'edit.flipHorizontal',
      label: 'Flip horizontal',
      category: 'Edit',
      keywords: ['mirror', 'flip', 'horizontal', 'reflect'],
      run: () => {
        const store = storeRef.current
        if (!store) return
        flipHorizontal(store, selectionRef.current.snapshot)
      },
    })
    list.push({
      id: 'edit.flipVertical',
      label: 'Flip vertical',
      category: 'Edit',
      keywords: ['mirror', 'flip', 'vertical', 'reflect'],
      run: () => {
        const store = storeRef.current
        if (!store) return
        flipVertical(store, selectionRef.current.snapshot)
      },
    })
    // Align (multi-element edge / centre snapping).
    for (const [axis, label, kw] of [
      ['left', 'Align left', ['left edge']],
      ['centreX', 'Align centre horizontally', ['middle', 'horizontal centre']],
      ['right', 'Align right', ['right edge']],
      ['top', 'Align top', ['top edge']],
      ['centreY', 'Align centre vertically', ['middle', 'vertical centre']],
      ['bottom', 'Align bottom', ['bottom edge']],
    ] as const) {
      list.push({
        id: `edit.align.${axis}`,
        label,
        category: 'Align',
        keywords: ['align', ...kw],
        run: () => {
          const store = storeRef.current
          if (!store) return
          align(store, selectionRef.current.snapshot, axis)
        },
      })
    }
    // Distribute (equal gaps between consecutive elements).
    list.push({
      id: 'edit.distribute.horizontal',
      label: 'Distribute horizontally',
      category: 'Align',
      keywords: ['distribute', 'space', 'horizontal', 'equal'],
      run: () => {
        const store = storeRef.current
        if (!store) return
        distribute(store, selectionRef.current.snapshot, 'horizontal')
      },
    })
    list.push({
      id: 'edit.distribute.vertical',
      label: 'Distribute vertically',
      category: 'Align',
      keywords: ['distribute', 'space', 'vertical', 'equal'],
      run: () => {
        const store = storeRef.current
        if (!store) return
        distribute(store, selectionRef.current.snapshot, 'vertical')
      },
    })
    // Import.
    list.push({
      id: 'import.json',
      label: 'Import JSON…',
      category: 'Import',
      keywords: ['json', 'open', 'load', 'rapidly', 'scene'],
      run: () => {
        const store = storeRef.current
        const renderer = rendererRef.current
        if (!store || !renderer) return
        const input = document.createElement('input')
        input.type = 'file'
        input.accept = 'application/json,.json'
        input.onchange = async () => {
          const file = input.files?.[0]
          if (!file) return
          const text = await file.text()
          const parsed = parseExportedScene(text)
          if (isImportError(parsed)) {
            window.alert(
              'Could not import — file is not a Rapidly Collab JSON ' +
                `export (${parsed.reason}).`,
            )
            return
          }
          // Centre the import on the viewport rather than dropping
          // every element at world origin (which would either pile on
          // top of an existing scene or land off-screen).
          const canvas = interactiveRef.current
          if (!canvas) return
          const rect = canvas.getBoundingClientRect()
          const center = renderer.screenToWorld(rect.width / 2, rect.height / 2)
          const bounds = computeBounds(parsed.elements)
          const offset = bounds
            ? {
                x: center.x - bounds.x - bounds.width / 2,
                y: center.y - bounds.y - bounds.height / 2,
              }
            : { x: 0, y: 0 }
          const ids = importScene(store, parsed, { offset })
          if (ids.length > 0) selectionRef.current.set(ids)
        }
        input.click()
      },
    })
    list.push({
      id: 'import.mermaid',
      label: 'Import Mermaid flowchart…',
      category: 'Import',
      keywords: ['mermaid', 'flowchart', 'graph', 'diagram'],
      run: () => {
        const store = storeRef.current
        const renderer = rendererRef.current
        if (!store || !renderer) return
        const input = window.prompt(
          'Paste a Mermaid flowchart (flowchart TD / LR / …):',
          'flowchart TD\n  A[Start] --> B{Decision}\n  B --> C[Yes]\n  B --> D[No]',
        )
        if (!input) return
        const diagram = parseMermaid(input)
        if (!diagram) {
          window.alert(
            'Could not parse — expected a line starting with ' +
              '"flowchart TD/LR/TB/BT/RL" or "graph ...".',
          )
          return
        }
        // Drop new elements near the viewport centre.
        const canvas = interactiveRef.current
        if (!canvas) return
        const rect = canvas.getBoundingClientRect()
        const center = renderer.screenToWorld(rect.width / 2, rect.height / 2)
        const parts = mermaidToElements(diagram, {
          originX: center.x - 200,
          originY: center.y - 100,
        })
        const created: string[] = []
        store.transact(() => {
          for (const p of parts) created.push(store.create(p))
        })
        selectionRef.current.set(created)
      },
    })
    list.push({
      id: 'import.embed',
      label: 'Add embed…',
      category: 'Import',
      keywords: ['embed', 'iframe', 'youtube', 'loom', 'figma', 'vimeo'],
      run: () => {
        const store = storeRef.current
        const renderer = rendererRef.current
        const canvas = interactiveRef.current
        if (!store || !renderer || !canvas) return
        const input = window.prompt(
          'Paste a YouTube / Loom / Figma / Vimeo URL:',
          '',
        )
        if (!input) return
        const trimmed = input.trim()
        if (!isEmbeddableUrl(trimmed)) {
          window.alert(
            'Embed URLs must come from one of: YouTube, Loom, Figma, Vimeo.',
          )
          return
        }
        const rect = canvas.getBoundingClientRect()
        const center = renderer.screenToWorld(rect.width / 2, rect.height / 2)
        // 16:9 default — matches the common video-embed aspect.
        const width = 480
        const height = 270
        const id = store.create({
          type: 'embed',
          x: center.x - width / 2,
          y: center.y - height / 2,
          width,
          height,
          url: trimmed,
          sandbox: EMBED_SANDBOX,
        })
        selectionRef.current.set([id])
      },
    })
    // Help.
    list.push({
      id: 'help.shortcuts',
      label: 'Show keyboard shortcuts',
      category: 'Help',
      shortcut: ['?'],
      run: () => setShortcutsOpen(true),
    })
    list.push({
      id: 'view.toggleGrid',
      label: 'Toggle grid',
      category: 'View',
      keywords: ['grid', 'snap', 'guides', 'show', 'hide'],
      run: () => {
        const r = rendererRef.current
        if (!r) return
        r.setGridEnabled(!r.isGridEnabled())
      },
    })
    list.push({
      id: 'view.copyViewOnlyLink',
      label: 'Copy view-only link',
      category: 'View',
      keywords: ['share', 'view', 'read-only', 'link', 'copy'],
      run: async () => {
        if (typeof window === 'undefined') return
        const url = withViewModeUrl(window.location.href)
        try {
          if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(url)
          } else {
            window.prompt('Copy this view-only link:', url)
          }
        } catch {
          window.prompt('Copy this view-only link:', url)
        }
      },
    })
    list.push({
      id: 'view.toggleSnapToObjects',
      label: 'Toggle snap to objects',
      category: 'View',
      keywords: ['snap', 'objects', 'align', 'guides', 'alignment'],
      run: () => {
        const r = rendererRef.current
        if (!r) return
        r.setSnapToObjectsEnabled(!r.isSnapToObjectsEnabled())
      },
    })
    for (const [direction, label, shortcut] of [
      ['in', 'Zoom in', ['Mod', '=']],
      ['out', 'Zoom out', ['Mod', '-']],
      ['reset', 'Reset zoom', ['Mod', '0']],
    ] as const) {
      list.push({
        id: `view.zoom.${direction}`,
        label,
        category: 'View',
        shortcut: [...shortcut],
        keywords: ['zoom', direction],
        run: () => {
          const renderer = rendererRef.current
          const canvas = interactiveRef.current
          if (!renderer || !canvas) return
          const rect = canvas.getBoundingClientRect()
          const next = viewportForKeyboardZoom(
            renderer.getViewport(),
            direction,
            rect.width,
            rect.height,
          )
          vpRef.current = next
          renderer.setViewport(next)
          setZoom(Math.round(next.scale * 100) / 100)
          publishViewport()
        },
      })
    }
    list.push({
      id: 'view.zoomToFit',
      label: 'Zoom to fit',
      category: 'View',
      keywords: ['zoom', 'fit', 'all', 'reset', 'show all'],
      run: () => {
        const renderer = rendererRef.current
        const store = storeRef.current
        const canvas = interactiveRef.current
        if (!renderer || !store || !canvas) return
        const rect = canvas.getBoundingClientRect()
        const vp = zoomToFit(store.list(), rect.width, rect.height)
        if (vp) renderer.setViewport(vp)
      },
    })
    list.push({
      id: 'view.zoomToSelection',
      label: 'Zoom to selection',
      category: 'View',
      keywords: ['zoom', 'selection', 'frame', 'focus'],
      run: () => {
        const renderer = rendererRef.current
        const store = storeRef.current
        const canvas = interactiveRef.current
        if (!renderer || !store || !canvas) return
        const rect = canvas.getBoundingClientRect()
        const vp = zoomToSelection(
          store.list(),
          selectionRef.current.snapshot,
          rect.width,
          rect.height,
        )
        if (vp) renderer.setViewport(vp)
      },
    })
    list.push({
      id: 'view.present',
      label: 'Start presentation mode',
      category: 'View',
      keywords: ['slideshow', 'talk', 'frame'],
      run: () => {
        setPresentationIndex(0)
        setPresentationActive(true)
      },
    })
    // View mode strips every editing command. Read-only-safe ids are
    // whitelisted in ``view-mode.ts`` so the palette stays useful for
    // export / zoom / help / tool toggles between hand and select.
    if (viewMode) return list.filter((c) => isReadOnlyPaletteCommand(c.id))
    return list
  }, [viewMode, publishViewport])
  const cursor = hoverCursorStyle ?? activeToolRef.current?.cursor ?? 'default'

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-50 dark:bg-slate-950">
      <ServiceWorkerRegistrar />
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-800 dark:bg-slate-900">
        <span className="font-semibold">Collab v2 demo</span>
        {viewMode ? (
          <span
            className="rounded-md border border-amber-400 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800 dark:border-amber-500/60 dark:bg-amber-950/40 dark:text-amber-200"
            aria-label="Read-only viewer mode"
          >
            View only
          </span>
        ) : null}
        <div
          role="radiogroup"
          aria-label="Active tool"
          className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800"
        >
          {TOOL_CHOICES.filter((t) => !viewMode || isReadOnlyTool(t.id)).map(
            (t) => (
              <button
                key={t.id}
                type="button"
                role="radio"
                aria-checked={t.id === toolId}
                onClick={() => setToolId(t.id)}
                className={
                  'rounded-md px-2 py-1 text-xs transition-colors sm:px-3 sm:text-sm ' +
                  (t.id === toolId
                    ? 'bg-white text-slate-900 shadow-xs dark:bg-slate-700 dark:text-slate-50'
                    : 'rp-text-secondary hover:rp-text-primary')
                }
              >
                {t.label}
              </button>
            ),
          )}
        </div>
        <span className="rp-text-secondary hidden md:inline">
          {activeChoice?.hint}
        </span>
        <span className="ml-auto flex items-center gap-3">
          {externalPresence ? null : (
            <>
              <label className="hidden items-center gap-1 text-xs lg:flex">
                <input
                  type="checkbox"
                  checked={demoPeerActive}
                  onChange={(e) => {
                    setDemoPeerActive(e.target.checked)
                    if (!e.target.checked) setFollowingDemoPeer(false)
                  }}
                />
                Demo peer cursor
              </label>
              <label className="hidden items-center gap-1 text-xs lg:flex">
                <input
                  type="checkbox"
                  checked={followingDemoPeer}
                  disabled={!demoPeerActive}
                  onChange={(e) => setFollowingDemoPeer(e.target.checked)}
                />
                Follow demo peer
              </label>
            </>
          )}
          <label className="hidden items-center gap-1 text-xs lg:flex">
            <input
              type="checkbox"
              checked={laserActive}
              onChange={(e) => setLaserActive(e.target.checked)}
            />
            Laser pointer
          </label>
          {selectionSize > 0 ? (
            <button
              type="button"
              onClick={() => setMobileStyleOpen(true)}
              aria-label="Open style panel"
              className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-slate-500 md:hidden dark:border-slate-700"
            >
              Style
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setShortcutsOpen(true)}
            aria-label="Show keyboard shortcuts"
            title="Shortcuts (?)"
            className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-slate-500 dark:border-slate-700"
          >
            ?
          </button>
          <button
            type="button"
            onClick={() => {
              setPresentationIndex(0)
              setPresentationActive(true)
            }}
            aria-label="Start presentation mode"
            title="Present (arrow keys, Esc to exit)"
            className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-slate-500 dark:border-slate-700"
          >
            Present
          </button>
          {canInstall ? (
            <button
              type="button"
              onClick={async () => {
                await installRef.current?.install()
              }}
              aria-label="Install Rapidly as an app"
              title="Install this app on your device"
              className="rounded-md border border-emerald-500 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-200"
            >
              Install app
            </button>
          ) : null}
          <button
            type="button"
            onClick={async () => {
              const store = storeRef.current
              if (!store) return
              const blob = await exportToPNG(store.list())
              if (blob) downloadBlob(blob, 'rapidly-collab.png')
            }}
            className="hidden rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-slate-500 sm:inline-block dark:border-slate-700"
          >
            Export PNG
          </button>
          <button
            type="button"
            onClick={() => {
              const store = storeRef.current
              if (!store) return
              const payload = exportToJSON(store.list())
              const blob = new Blob([JSON.stringify(payload, null, 2)], {
                type: 'application/json',
              })
              downloadBlob(blob, 'rapidly-collab.json')
            }}
            className="hidden rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-slate-500 sm:inline-block dark:border-slate-700"
          >
            Export JSON
          </button>
          <button
            type="button"
            onClick={() => {
              const store = storeRef.current
              if (!store) return
              const svg = exportToSVG(store.list())
              const blob = new Blob([svg], { type: 'image/svg+xml' })
              downloadBlob(blob, 'rapidly-collab.svg')
            }}
            className="hidden rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-slate-500 sm:inline-block dark:border-slate-700"
          >
            Export SVG
          </button>
          {/* ""More"" disclosure for narrow viewports — gives touch
              users a way to reach the toggles + exports that are
              hidden above without squeezing the toolbar. */}
          <details className="relative lg:hidden">
            <summary
              className="cursor-pointer list-none rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-slate-500 dark:border-slate-700"
              aria-label="More actions"
            >
              ⋯
            </summary>
            <div className="absolute right-0 z-20 mt-1 flex min-w-[180px] flex-col gap-2 rounded-md border border-slate-200 bg-white p-3 text-xs shadow-lg dark:border-slate-700 dark:bg-slate-900">
              {externalPresence ? null : (
                <>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={demoPeerActive}
                      onChange={(e) => {
                        setDemoPeerActive(e.target.checked)
                        if (!e.target.checked) setFollowingDemoPeer(false)
                      }}
                    />
                    Demo peer cursor
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={followingDemoPeer}
                      disabled={!demoPeerActive}
                      onChange={(e) => setFollowingDemoPeer(e.target.checked)}
                    />
                    Follow demo peer
                  </label>
                </>
              )}
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={laserActive}
                  onChange={(e) => setLaserActive(e.target.checked)}
                />
                Laser pointer
              </label>
              <button
                type="button"
                onClick={async () => {
                  const store = storeRef.current
                  if (!store) return
                  const blob = await exportToPNG(store.list())
                  if (blob) downloadBlob(blob, 'rapidly-collab.png')
                }}
                className="rounded-md border border-slate-300 px-2 py-1 text-left hover:border-slate-500 sm:hidden dark:border-slate-700"
              >
                Export PNG
              </button>
              <button
                type="button"
                onClick={() => {
                  const store = storeRef.current
                  if (!store) return
                  const payload = exportToJSON(store.list())
                  const blob = new Blob([JSON.stringify(payload, null, 2)], {
                    type: 'application/json',
                  })
                  downloadBlob(blob, 'rapidly-collab.json')
                }}
                className="rounded-md border border-slate-300 px-2 py-1 text-left hover:border-slate-500 sm:hidden dark:border-slate-700"
              >
                Export JSON
              </button>
              <button
                type="button"
                onClick={() => {
                  const store = storeRef.current
                  if (!store) return
                  const svg = exportToSVG(store.list())
                  const blob = new Blob([svg], { type: 'image/svg+xml' })
                  downloadBlob(blob, 'rapidly-collab.svg')
                }}
                className="rounded-md border border-slate-300 px-2 py-1 text-left hover:border-slate-500 sm:hidden dark:border-slate-700"
              >
                Export SVG
              </button>
            </div>
          </details>
          <span className="rp-text-secondary hidden md:inline">
            elements:{' '}
            <span className="rp-text-primary font-mono">{elementCount}</span>
          </span>
          <span className="rp-text-secondary hidden md:inline">
            selected:{' '}
            <span className="rp-text-primary font-mono">{selectionSize}</span>
          </span>
          <span className="rp-text-secondary hidden sm:inline">
            zoom:{' '}
            <span className="rp-text-primary font-mono">
              {zoom.toFixed(2)}×
            </span>
          </span>
        </span>
      </div>
      <div className="flex flex-1">
        <div className="relative flex-1">
          <canvas
            ref={staticRef}
            className="absolute inset-0 h-full w-full"
            aria-hidden
          />
          <canvas
            ref={interactiveRef}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            onDoubleClick={onDoubleClick}
            onWheel={onWheel}
            onDragOver={onDragOver}
            onDrop={onDrop}
            className="absolute inset-0 h-full w-full touch-none"
            style={{ cursor }}
            aria-label="Renderer demo canvas"
          />
          {editingId && storeRef.current && rendererRef.current ? (
            <TextEditor
              key={editingId}
              id={editingId}
              store={storeRef.current}
              renderer={rendererRef.current}
              onDone={() => setEditingId(null)}
            />
          ) : null}
          {storeRef.current && rendererRef.current ? (
            <HyperlinkBadge
              store={storeRef.current}
              selection={selectionRef.current}
              renderer={rendererRef.current}
            />
          ) : null}
          {storeRef.current && rendererRef.current ? (
            <EmbedsOverlay
              store={storeRef.current}
              renderer={rendererRef.current}
            />
          ) : null}
        </div>
        {storeRef.current ? (
          <div className="hidden md:flex">
            <PropertiesPanel
              store={storeRef.current}
              selection={selectionRef.current}
            />
          </div>
        ) : null}
      </div>
      <ShortcutsOverlay
        open={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />
      <CommandPalette
        open={paletteOpen}
        commands={commands}
        onClose={() => setPaletteOpen(false)}
      />
      {storeRef.current ? (
        <MobilePropertiesSheet
          open={mobileStyleOpen}
          store={storeRef.current}
          selection={selectionRef.current}
          onClose={() => setMobileStyleOpen(false)}
        />
      ) : null}
      {presentationActive ? (
        <div
          role="status"
          className="pointer-events-none fixed inset-x-0 top-0 z-40 flex items-center justify-between bg-slate-900/70 px-4 py-2 text-xs text-slate-100 backdrop-blur-sm"
        >
          <span>Presentation mode — frame {presentationIndex + 1}</span>
          <span className="rp-text-secondary">← / → arrows · Esc to exit</span>
        </div>
      ) : null}
    </div>
  )
}

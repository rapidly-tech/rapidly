'use client'

/**
 * Collab v2 renderer demo page.
 *
 * Phase 3b adds selection + delete on top of the tool system:
 *  - Select tool: click / shift-click / marquee
 *  - Backspace or Delete removes all selected elements
 *  - Live bounding-box overlay on the interactive canvas
 *
 * All mutations still ride the ``ElementStore`` → Yjs → renderer
 * observe path production chambers will use.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as Y from 'yjs'

import {
  copy as clipboardCopy,
  cut as clipboardCut,
  duplicate as clipboardDuplicate,
  paste as clipboardPaste,
  getClipboard,
} from '@/utils/collab/clipboard'
import { type Command } from '@/utils/collab/command-palette'
import { makeCursorOverlay } from '@/utils/collab/cursor-overlay'
import {
  createElementStore,
  type ElementStore,
} from '@/utils/collab/element-store'
import { downloadBlob, exportToJSON, exportToPNG } from '@/utils/collab/export'
import {
  createFollowMeController,
  type FollowMeController,
} from '@/utils/collab/follow-me'
import { expandToGroups, group, ungroup } from '@/utils/collab/groups'
import { setLink } from '@/utils/collab/hyperlinks'
import {
  createImageElement,
  extractPastedImage,
} from '@/utils/collab/image-paste'
import {
  createInstallPromptController,
  type InstallPromptController,
} from '@/utils/collab/install-prompt'
import { createLaserState, type LaserController } from '@/utils/collab/laser'
import { makeLaserOverlay } from '@/utils/collab/laser-overlay'
import { filterUnlocked, toggleLock } from '@/utils/collab/locks'
import { mermaidToElements, parseMermaid } from '@/utils/collab/mermaid'
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
import { onEditRequest } from '@/utils/collab/text-editing'
import { toolIdForKey } from '@/utils/collab/tool-keys'
import {
  currentMarqueeRect,
  hoverCursor,
  toolFor,
  type SelectToolCtx,
  type Tool,
  type ToolCtx,
  type ToolId,
} from '@/utils/collab/tools'
import { createUndoManager, type UndoController } from '@/utils/collab/undo'
import { makeViewport, zoomAt, type Viewport } from '@/utils/collab/viewport'
import { animateViewport } from '@/utils/collab/viewport-transitions'
import {
  bringForward,
  bringToFront,
  sendBackward,
  sendToBack,
} from '@/utils/collab/z-order'

import { CommandPalette } from './CommandPalette'
import { HyperlinkBadge } from './HyperlinkBadge'
import { MobilePropertiesSheet } from './MobilePropertiesSheet'
import { PropertiesPanel } from './PropertiesPanel'
import { ServiceWorkerRegistrar } from './ServiceWorkerRegistrar'
import { ShortcutsOverlay } from './ShortcutsOverlay'
import { TextEditor } from './TextEditor'

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
]

interface CollabRenderDemoProps {
  /** Optional externally-owned Y.Doc. When provided, the demo binds
   *  to it instead of creating its own — used by the chamber to host
   *  this component over a real ``useCollabRoom`` session. The caller
   *  owns the doc's lifecycle in that case; the demo will **not**
   *  destroy it on unmount. */
  doc?: Y.Doc
}

export function CollabRenderDemo({
  doc: externalDoc,
}: CollabRenderDemoProps = {}) {
  const staticRef = useRef<HTMLCanvasElement | null>(null)
  const interactiveRef = useRef<HTMLCanvasElement | null>(null)
  const rendererRef = useRef<Renderer | null>(null)
  const storeRef = useRef<ElementStore | null>(null)
  const selectionRef = useRef<SelectionState>(new SelectionState())
  const activeToolRef = useRef<Tool | null>(null)
  const gestureToolRef = useRef<Tool | null>(null)
  const vpRef = useRef<Viewport>(makeViewport({ scrollX: -20, scrollY: -20 }))
  const presenceRef = useRef<InMemoryPresenceSource>(inMemoryPresenceSource())
  const demoPeerFrameRef = useRef<number | null>(null)
  const followControllerRef = useRef<FollowMeController | null>(null)
  const undoRef = useRef<UndoController | null>(null)
  const laserRef = useRef<LaserController | null>(null)
  const installRef = useRef<InstallPromptController | null>(null)
  const pinchRef = useRef<PinchPanGesture>(createPinchPanGesture())
  const precisionRef = useRef<PointerPrecision>('fine')

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
  }, [demoPeerActive])

  useEffect(() => {
    activeToolRef.current = toolFor(toolId)
  }, [toolId])

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
    const cursorPaint = makeCursorOverlay({
      source: presenceRef.current,
      getViewport: () => r.getViewport(),
    })
    const remoteSelectionPaint = makeRemoteSelectionOverlay({
      store,
      source: presenceRef.current,
      getViewport: () => r.getViewport(),
    })
    const laserPaint = makeLaserOverlay({
      source: presenceRef.current,
      getViewport: () => r.getViewport(),
    })
    r.setInteractivePaint((ctx) => {
      // Paint order: remote selections sit below the local dashed
      // overlay; laser trails layer above selections but below cursors
      // so the pointer itself stays crisp on top; cursors sit above
      // everything.
      remoteSelectionPaint(ctx)
      selectionPaint(ctx)
      laserPaint(ctx)
      cursorPaint(ctx)
    })

    // Re-paint whenever a remote cursor updates.
    const unsubscribePresence = presenceRef.current.subscribe(() => {
      r.invalidate()
    })

    // Follow-me controller writes the target peer's viewport into
    // our live viewport object and repaints. Calling ``setTarget``
    // from the UI below activates it; ``null`` tears it off.
    const follow = createFollowMeController({
      source: presenceRef.current,
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
      },
    })
    return () => handle.cancel()
  }, [presentationActive, presentationIndex])

  // Laser mode: prune the trail on every RAF while active so the
  // tail fades away even when the user stops moving.
  useEffect(() => {
    if (!laserActive) {
      laserRef.current?.clear()
      presenceRef.current.removeRemote(999)
      return
    }
    let handle = 0
    const tick = (): void => {
      const laser = laserRef.current
      const renderer = rendererRef.current
      if (laser && renderer) {
        const snap = laser.snapshot(performance.now())
        if (snap.points.length > 0) {
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
      }
      handle = requestAnimationFrame(tick)
    }
    handle = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(handle)
    }
  }, [laserActive])

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
    [toolCtx, toolId, laserActive],
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

  const onWheel = useCallback((e: React.WheelEvent) => {
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
  }, [])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
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
        } else if (key === 'x') {
          if (selection.size === 0) return
          e.preventDefault()
          clipboardCut(store, selection.snapshot)
          selection.clear()
        } else if (key === 'v') {
          const payload = getClipboard()
          if (!payload) return
          e.preventDefault()
          const newIds = clipboardPaste(store, payload)
          if (newIds.length > 0) selection.set(newIds)
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
  }, [toolCtx, presentationActive])

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
    // Import.
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
    // Help.
    list.push({
      id: 'help.shortcuts',
      label: 'Show keyboard shortcuts',
      category: 'Help',
      shortcut: ['?'],
      run: () => setShortcutsOpen(true),
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
    return list
  }, [])
  const cursor = hoverCursorStyle ?? activeToolRef.current?.cursor ?? 'default'

  return (
    <div className="flex h-screen w-screen flex-col bg-slate-50 dark:bg-slate-950">
      <ServiceWorkerRegistrar />
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-800 dark:bg-slate-900">
        <span className="font-semibold">Collab v2 demo</span>
        <div
          role="radiogroup"
          aria-label="Active tool"
          className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800"
        >
          {TOOL_CHOICES.map((t) => (
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
          ))}
        </div>
        <span className="rp-text-secondary hidden md:inline">
          {activeChoice?.hint}
        </span>
        <span className="ml-auto flex items-center gap-3">
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

'use client'

/**
 * Modal crop editor for an ``ImageElement``.
 *
 * Shows the full-resolution image with a draggable + resizable crop
 * rectangle on top. Apply commits the rectangle to the element's
 * ``crop`` field (in natural-image pixel coords); Cancel discards.
 *
 * Why a modal rather than in-canvas editing? A modal sidesteps the
 * tool/gesture system entirely — no new ``ToolId``, no extra state on
 * the active-gesture machinery — at the cost of being a separate
 * surface. v1 trades complexity for shipping. An in-canvas edit pass
 * can land later if the modal feels heavy.
 *
 * Accessibility
 * -------------
 *  - ``role=dialog`` + ``aria-modal`` + ``aria-labelledby``
 *  - Apply / Cancel are real buttons, both Enter and Escape are wired
 *  - Focus moves to Apply on open and restores on close
 */

import { useEffect, useMemo, useRef, useState } from 'react'

interface CropRect {
  x: number
  y: number
  width: number
  height: number
}

interface Props {
  open: boolean
  /** Original (uncropped) data URL — the picker shows the full image. */
  dataUrl: string
  naturalWidth: number
  naturalHeight: number
  /** Existing crop, if any. Defaults to the full image. */
  initialCrop?: CropRect
  onApply: (crop: CropRect) => void
  onCancel: () => void
}

const PREVIEW_MAX = 480 // CSS pixels — the modal's image preview cap

export function ImageCropDialog({
  open,
  dataUrl,
  naturalWidth,
  naturalHeight,
  initialCrop,
  onApply,
  onCancel,
}: Props) {
  const applyBtn = useRef<HTMLButtonElement | null>(null)
  const previousFocus = useRef<HTMLElement | null>(null)

  // Display scale: how many CSS preview pixels per natural pixel.
  // We render the image at min(natural, PREVIEW_MAX) on the longest
  // side and the crop rect rides the same coordinate system.
  const scale = useMemo(() => {
    const longest = Math.max(naturalWidth, naturalHeight)
    return Math.min(1, PREVIEW_MAX / longest)
  }, [naturalWidth, naturalHeight])

  const previewW = Math.round(naturalWidth * scale)
  const previewH = Math.round(naturalHeight * scale)

  const [crop, setCrop] = useState<CropRect>(
    initialCrop ?? {
      x: 0,
      y: 0,
      width: naturalWidth,
      height: naturalHeight,
    },
  )
  // Reset crop when the dialog re-opens for a different image.
  useEffect(() => {
    if (!open) return
    setCrop(
      initialCrop ?? {
        x: 0,
        y: 0,
        width: naturalWidth,
        height: naturalHeight,
      },
    )
  }, [open, initialCrop, naturalWidth, naturalHeight])

  useEffect(() => {
    if (!open) return
    previousFocus.current = document.activeElement as HTMLElement | null
    applyBtn.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onCancel()
      } else if (e.key === 'Enter') {
        e.preventDefault()
        onApply(crop)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previousFocus.current?.focus?.()
    }
  }, [open, onApply, onCancel, crop])

  if (!open) return null

  return (
    <div
      role="presentation"
      onClick={onCancel}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="collab-crop-title"
        onClick={(e) => e.stopPropagation()}
        className="flex max-w-[640px] flex-col gap-4 rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="flex items-center justify-between">
          <h2
            id="collab-crop-title"
            className="text-lg font-semibold text-slate-900 dark:text-slate-100"
          >
            Crop image
          </h2>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close crop dialog"
            className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            ✕
          </button>
        </div>

        <CropCanvas
          dataUrl={dataUrl}
          naturalWidth={naturalWidth}
          naturalHeight={naturalHeight}
          previewW={previewW}
          previewH={previewH}
          scale={scale}
          crop={crop}
          onChange={setCrop}
        />

        <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span>
            {Math.round(crop.width)} × {Math.round(crop.height)} px
            {' · '}
            from {Math.round(crop.x)}, {Math.round(crop.y)}
          </span>
          <button
            type="button"
            onClick={() =>
              setCrop({
                x: 0,
                y: 0,
                width: naturalWidth,
                height: naturalHeight,
              })
            }
            className="rounded-md px-2 py-1 text-xs text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Reset crop
          </button>
        </div>

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            Cancel
          </button>
          <button
            ref={applyBtn}
            type="button"
            onClick={() => onApply(crop)}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  )
}

interface CanvasProps {
  dataUrl: string
  naturalWidth: number
  naturalHeight: number
  previewW: number
  previewH: number
  scale: number
  crop: CropRect
  onChange: (next: CropRect) => void
}

type DragKind = 'move' | 'nw' | 'ne' | 'sw' | 'se' | null

function CropCanvas({
  dataUrl,
  naturalWidth,
  naturalHeight,
  previewW,
  previewH,
  scale,
  crop,
  onChange,
}: CanvasProps) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [drag, setDrag] = useState<{
    kind: DragKind
    startX: number
    startY: number
    startCrop: CropRect
  } | null>(null)

  useEffect(() => {
    if (!drag) return
    // Convert preview-space pixels back to natural-image coords.
    const toNatural = (px: number) => Math.round(px / scale)
    const onMove = (e: PointerEvent) => {
      const rect = ref.current?.getBoundingClientRect()
      if (!rect) return
      const dx = e.clientX - drag.startX
      const dy = e.clientY - drag.startY
      let next = { ...drag.startCrop }
      if (drag.kind === 'move') {
        next.x = clamp(
          drag.startCrop.x + toNatural(dx),
          0,
          naturalWidth - drag.startCrop.width,
        )
        next.y = clamp(
          drag.startCrop.y + toNatural(dy),
          0,
          naturalHeight - drag.startCrop.height,
        )
      } else {
        const nx = drag.kind === 'nw' || drag.kind === 'sw'
        const ny = drag.kind === 'nw' || drag.kind === 'ne'
        const ndx = toNatural(dx)
        const ndy = toNatural(dy)
        let x = drag.startCrop.x
        let y = drag.startCrop.y
        let w = drag.startCrop.width
        let h = drag.startCrop.height
        if (nx) {
          x = clamp(
            drag.startCrop.x + ndx,
            0,
            drag.startCrop.x + drag.startCrop.width - 8,
          )
          w = drag.startCrop.x + drag.startCrop.width - x
        } else {
          w = clamp(
            drag.startCrop.width + ndx,
            8,
            naturalWidth - drag.startCrop.x,
          )
        }
        if (ny) {
          y = clamp(
            drag.startCrop.y + ndy,
            0,
            drag.startCrop.y + drag.startCrop.height - 8,
          )
          h = drag.startCrop.y + drag.startCrop.height - y
        } else {
          h = clamp(
            drag.startCrop.height + ndy,
            8,
            naturalHeight - drag.startCrop.y,
          )
        }
        next = { x, y, width: w, height: h }
      }
      onChange(next)
    }
    const onUp = () => setDrag(null)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [drag, naturalWidth, naturalHeight, scale, onChange])

  // Render the crop rectangle in preview-space.
  const left = crop.x * scale
  const top = crop.y * scale
  const width = crop.width * scale
  const height = crop.height * scale

  return (
    <div
      ref={ref}
      className="relative overflow-hidden rounded-md border border-slate-200 dark:border-slate-700"
      style={{ width: previewW, height: previewH }}
    >
      {/* Plain <img> rather than the project's UploadImage / StaticImage —
          this is a transient, modal-local preview of a base64 data URL
          that the user just selected, with no upload pipeline or CDN
          involvement, so the project image components don't apply. */}
      {/* eslint-disable-next-line @next/next/no-img-element, no-restricted-syntax */}
      <img
        src={dataUrl}
        alt=""
        draggable={false}
        style={{ width: previewW, height: previewH }}
        className="select-none"
      />
      {/* Dim the area outside the crop. Four overlay rects beats a
          single mask because we don't need the SVG `<mask>` element
          and overlap-free maths is cheap. */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: 'rgba(15, 23, 42, 0.45)',
          clipPath: `polygon(
            0 0, 100% 0, 100% 100%, 0 100%, 0 0,
            ${left}px ${top}px,
            ${left}px ${top + height}px,
            ${left + width}px ${top + height}px,
            ${left + width}px ${top}px,
            ${left}px ${top}px
          )`,
        }}
      />
      {/* Crop rectangle: drag to move, corners to resize. */}
      <div
        className="absolute cursor-move border-2 border-emerald-500"
        style={{ left, top, width, height }}
        onPointerDown={(e) => {
          e.preventDefault()
          setDrag({
            kind: 'move',
            startX: e.clientX,
            startY: e.clientY,
            startCrop: { ...crop },
          })
        }}
      >
        {(['nw', 'ne', 'sw', 'se'] as const).map((corner) => (
          <button
            key={corner}
            type="button"
            aria-label={`Resize crop ${corner}`}
            onPointerDown={(e) => {
              e.preventDefault()
              e.stopPropagation()
              setDrag({
                kind: corner,
                startX: e.clientX,
                startY: e.clientY,
                startCrop: { ...crop },
              })
            }}
            className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-sm border border-emerald-700 bg-white"
            style={{
              left: corner.includes('w') ? 0 : '100%',
              top: corner.includes('n') ? 0 : '100%',
              cursor:
                corner === 'nw' || corner === 'se'
                  ? 'nwse-resize'
                  : 'nesw-resize',
            }}
          />
        ))}
      </div>
    </div>
  )
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v))
}

'use client'

/**
 * Right-hand properties panel for the Collab v2 demo.
 *
 * Shows controls for the common style fields of the current
 * selection:
 *  - Stroke colour (swatches)
 *  - Fill colour (swatches + "transparent" tile)
 *  - Stroke width (three presets)
 *  - Roughness (0 / 1 / 2)
 *  - Opacity (slider)
 *
 * When a field has different values across the selection the
 * corresponding control shows an indeterminate dash.
 */

import { useEffect, useState } from 'react'

import type { ElementStore } from '@/utils/collab/element-store'
import {
  applyToSelection,
  FILL_PALETTE,
  ROUGHNESS_LEVELS,
  sharedField,
  STROKE_PALETTE,
  STROKE_WIDTHS,
  type SharedValue,
} from '@/utils/collab/properties'
import type { SelectionState } from '@/utils/collab/selection'

interface Props {
  store: ElementStore
  selection: SelectionState
}

export function PropertiesPanel({ store, selection }: Props) {
  // Force re-render on selection or store change so shared values
  // stay fresh without prop-drilling them from the parent.
  const [, tick] = useState(0)
  useEffect(() => {
    const off1 = selection.subscribe(() => tick((n) => n + 1))
    const off2 = store.observe(() => tick((n) => n + 1))
    return () => {
      off1()
      off2()
    }
  }, [store, selection])

  if (selection.size === 0) {
    return (
      <aside className="flex w-60 flex-col gap-3 border-l border-slate-200 bg-white p-4 text-sm dark:border-slate-800 dark:bg-slate-900">
        <span className="rp-text-secondary">Nothing selected</span>
      </aside>
    )
  }

  const ids = selection.snapshot
  const strokeColor = sharedField(store, ids, 'strokeColor')
  const fillColor = sharedField(store, ids, 'fillColor')
  const strokeWidth = sharedField(store, ids, 'strokeWidth')
  const roughness = sharedField(store, ids, 'roughness')
  const opacity = sharedField(store, ids, 'opacity')

  return (
    <aside className="flex w-60 flex-col gap-5 border-l border-slate-200 bg-white p-4 text-sm dark:border-slate-800 dark:bg-slate-900">
      <FieldGroup label="Stroke">
        <Swatches
          palette={STROKE_PALETTE}
          value={strokeColor}
          onChange={(c) => applyToSelection(store, ids, { strokeColor: c })}
        />
      </FieldGroup>

      <FieldGroup label="Fill">
        <Swatches
          palette={FILL_PALETTE}
          value={fillColor}
          onChange={(c) =>
            applyToSelection(store, ids, {
              fillColor: c,
              // Toggle fillStyle to match: transparent → none,
              // anything else → solid. A fuller hatch/dots picker
              // can come with a proper Phase 8b.
              fillStyle: c === 'transparent' ? 'none' : 'solid',
            })
          }
        />
      </FieldGroup>

      <FieldGroup label="Stroke width">
        <Row>
          {STROKE_WIDTHS.map((w) => (
            <PillButton
              key={w}
              active={strokeWidth === w}
              onClick={() => applyToSelection(store, ids, { strokeWidth: w })}
            >
              <span
                className="inline-block bg-current align-middle"
                style={{ width: 20, height: `${w}px`, borderRadius: 999 }}
              />
            </PillButton>
          ))}
          {strokeWidth === 'mixed' && <Mixed />}
        </Row>
      </FieldGroup>

      <FieldGroup label="Roughness">
        <Row>
          {ROUGHNESS_LEVELS.map((r) => (
            <PillButton
              key={r}
              active={roughness === r}
              onClick={() => applyToSelection(store, ids, { roughness: r })}
            >
              {r === 0 ? 'Clean' : r === 1 ? 'Normal' : 'Sketch'}
            </PillButton>
          ))}
          {roughness === 'mixed' && <Mixed />}
        </Row>
      </FieldGroup>

      <FieldGroup label="Opacity">
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={typeof opacity === 'number' ? opacity : 100}
          onChange={(e) =>
            applyToSelection(store, ids, { opacity: Number(e.target.value) })
          }
          aria-label="Opacity"
          className="w-full"
        />
        <div className="rp-text-secondary flex items-center justify-between text-xs">
          <span>{opacity === 'mixed' ? 'mixed' : `${opacity ?? 100}%`}</span>
          <span>{ids.size} selected</span>
        </div>
      </FieldGroup>
    </aside>
  )
}

// ── Small local primitives ──────────────────────────────────────────

function FieldGroup({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="rp-text-secondary text-xs font-medium tracking-wide uppercase">
        {label}
      </span>
      {children}
    </div>
  )
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-1.5">{children}</div>
}

function Swatches({
  palette,
  value,
  onChange,
}: {
  palette: readonly string[]
  value: SharedValue<string>
  onChange: (c: string) => void
}) {
  return (
    <Row>
      {palette.map((c) => (
        <button
          key={c}
          type="button"
          aria-label={c}
          onClick={() => onChange(c)}
          className={
            'h-7 w-7 rounded-md border transition ' +
            (value === c
              ? 'border-indigo-500 ring-2 ring-indigo-500/40'
              : 'border-slate-300 hover:border-slate-500 dark:border-slate-700')
          }
          style={{
            backgroundColor: c === 'transparent' ? undefined : c,
            backgroundImage:
              c === 'transparent'
                ? 'repeating-linear-gradient(45deg, #f1f5f9 0 6px, #fff 6px 12px)'
                : undefined,
          }}
        />
      ))}
      {value === 'mixed' && <Mixed />}
    </Row>
  )
}

function PillButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'rounded-md border px-2 py-1 text-xs transition ' +
        (active
          ? 'border-indigo-500 bg-indigo-50 text-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-100'
          : 'border-slate-300 hover:border-slate-500 dark:border-slate-700')
      }
    >
      {children}
    </button>
  )
}

function Mixed() {
  return (
    <span
      className="rp-text-muted text-xs italic"
      aria-label="mixed values across selection"
    >
      mixed
    </span>
  )
}

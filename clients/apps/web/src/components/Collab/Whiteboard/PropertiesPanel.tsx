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
  CONVERTIBLE_TYPES,
  FILL_PALETTE,
  FILL_STYLES,
  FONT_FAMILIES,
  FONT_SIZES,
  ROUGHNESS_LEVELS,
  ROUNDNESS_PRESETS,
  sharedField,
  STROKE_PALETTE,
  STROKE_STYLES,
  STROKE_WIDTHS,
  TEXT_ALIGNMENTS,
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
  const fillStyle = sharedField(store, ids, 'fillStyle')
  const strokeWidth = sharedField(store, ids, 'strokeWidth')
  const strokeStyle = sharedField(store, ids, 'strokeStyle')
  const roughness = sharedField(store, ids, 'roughness')
  const opacity = sharedField(store, ids, 'opacity')
  // ``roundness`` is only on rect + diamond, so it isn't on
  // ``BaseElement``. Probe the selection by hand and only show the
  // picker when at least one element actually supports it.
  const roundness = sharedRoundness(store, ids)
  const showRoundness = roundness !== null
  // Text-only fields (fontFamily / fontSize / textAlign) live on
  // text + sticky elements. Same per-element probe pattern; the
  // group is hidden entirely when no text-bearing element is in
  // the selection so shape-only selections stay compact.
  const fontFamily = sharedTextField<string>(store, ids, 'fontFamily')
  const fontSize = sharedTextField<number>(store, ids, 'fontSize')
  const textAlign = sharedTextField<string>(store, ids, 'textAlign')
  const showText =
    fontFamily !== null || fontSize !== null || textAlign !== null
  // Convert picker only shows for a single rect/ellipse/diamond.
  // Multi-selection or sticky/text/freedraw/etc. would need extra
  // structural translation we don't try to do silently.
  const convertibleId = singleConvertibleId(store, ids)
  const convertibleType = convertibleId
    ? ((store.get(convertibleId) as { type: string } | null)?.type ?? null)
    : null

  return (
    <aside className="flex w-60 flex-col gap-5 border-l border-slate-200 bg-white p-4 text-sm dark:border-slate-800 dark:bg-slate-900">
      {convertibleId && convertibleType && (
        <FieldGroup label="Convert to">
          <Row>
            {CONVERTIBLE_TYPES.filter((t) => t.id !== convertibleType).map(
              (t) => (
                <PillButton
                  key={t.id}
                  active={false}
                  onClick={() => store.update(convertibleId, { type: t.id })}
                >
                  {t.label}
                </PillButton>
              ),
            )}
          </Row>
        </FieldGroup>
      )}

      <FieldGroup label="Stroke">
        <Swatches
          palette={STROKE_PALETTE}
          value={strokeColor}
          onChange={(c) => applyToSelection(store, ids, { strokeColor: c })}
          onPick={(c) => applyToSelection(store, ids, { strokeColor: c })}
        />
      </FieldGroup>

      <FieldGroup label="Fill">
        <Swatches
          palette={FILL_PALETTE}
          value={fillColor}
          onChange={(c) =>
            applyToSelection(store, ids, {
              // Picking transparent collapses the fill to ``none``;
              // picking any colour promotes a previously-``none`` fill
              // back to ``solid`` so the colour is actually visible.
              // The fill-style picker below lets the user pick
              // hatch / cross-hatch / dots after a colour is set.
              fillColor: c,
              fillStyle:
                c === 'transparent'
                  ? 'none'
                  : fillStyle === 'none' ||
                      fillStyle === 'mixed' ||
                      fillStyle === null
                    ? 'solid'
                    : fillStyle,
            })
          }
          onPick={(c) =>
            applyToSelection(store, ids, {
              fillColor: c,
              fillStyle:
                fillStyle === 'none' ||
                fillStyle === 'mixed' ||
                fillStyle === null
                  ? 'solid'
                  : fillStyle,
            })
          }
        />
      </FieldGroup>

      {fillColor !== 'transparent' && fillStyle !== 'none' && (
        <FieldGroup label="Fill style">
          <Row>
            {FILL_STYLES.map((s) => (
              <PillButton
                key={s.id}
                active={fillStyle === s.id}
                onClick={() =>
                  applyToSelection(store, ids, { fillStyle: s.id })
                }
              >
                <span aria-label={s.aria}>{s.label}</span>
              </PillButton>
            ))}
            {fillStyle === 'mixed' && <Mixed />}
          </Row>
        </FieldGroup>
      )}

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

      <FieldGroup label="Stroke style">
        <Row>
          {STROKE_STYLES.map((s) => (
            <PillButton
              key={s}
              active={strokeStyle === s}
              onClick={() => applyToSelection(store, ids, { strokeStyle: s })}
            >
              <span
                className="inline-block align-middle"
                aria-hidden
                style={{
                  width: 28,
                  height: 0,
                  borderTopWidth: 2,
                  borderTopStyle: s,
                  borderColor: 'currentColor',
                }}
              />
            </PillButton>
          ))}
          {strokeStyle === 'mixed' && <Mixed />}
        </Row>
      </FieldGroup>

      {showRoundness && (
        <FieldGroup label="Edges">
          <Row>
            {ROUNDNESS_PRESETS.map((p) => (
              <PillButton
                key={p.id}
                active={roundness === p.value}
                onClick={() =>
                  applyToSelection(store, ids, { roundness: p.value })
                }
              >
                {p.label}
              </PillButton>
            ))}
            {roundness === 'mixed' && <Mixed />}
          </Row>
        </FieldGroup>
      )}

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

      {showText && (
        <>
          <FieldGroup label="Font">
            <Row>
              {FONT_FAMILIES.map((f) => (
                <PillButton
                  key={f.id}
                  active={fontFamily === f.id}
                  onClick={() =>
                    applyToSelection(store, ids, { fontFamily: f.id })
                  }
                >
                  <span
                    style={{
                      fontFamily:
                        f.id === 'mono'
                          ? 'ui-monospace, monospace'
                          : f.id === 'sans'
                            ? 'ui-sans-serif, system-ui, sans-serif'
                            : 'cursive',
                    }}
                  >
                    {f.label}
                  </span>
                </PillButton>
              ))}
              {fontFamily === 'mixed' && <Mixed />}
            </Row>
          </FieldGroup>

          <FieldGroup label="Font size">
            <Row>
              {FONT_SIZES.map((s) => (
                <PillButton
                  key={s.id}
                  active={fontSize === s.value}
                  onClick={() =>
                    applyToSelection(store, ids, { fontSize: s.value })
                  }
                >
                  {s.label}
                </PillButton>
              ))}
              {fontSize === 'mixed' && <Mixed />}
            </Row>
          </FieldGroup>

          <FieldGroup label="Text align">
            <Row>
              {TEXT_ALIGNMENTS.map((a) => (
                <PillButton
                  key={a.id}
                  active={textAlign === a.id}
                  onClick={() =>
                    applyToSelection(store, ids, { textAlign: a.id })
                  }
                >
                  <span aria-label={a.aria}>{a.label}</span>
                </PillButton>
              ))}
              {textAlign === 'mixed' && <Mixed />}
            </Row>
          </FieldGroup>
        </>
      )}
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
  onPick,
}: {
  palette: readonly string[]
  value: SharedValue<string>
  onChange: (c: string) => void
  /** Optional eye-dropper handler. When provided AND the browser
   *  exposes ``window.EyeDropper`` (Chrome / Edge as of writing),
   *  a small picker button is shown after the swatches. */
  onPick?: (c: string) => void
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
      {onPick && <EyeDropperButton onPick={onPick} />}
      {value === 'mixed' && <Mixed />}
    </Row>
  )
}

/** Eye-dropper button — feature-detects ``window.EyeDropper`` (the
 *  native HTML EyeDropper API, available in Chromium-based browsers).
 *  Falls back to nothing when unsupported so Safari/Firefox users
 *  don't see a non-functional button. */
function EyeDropperButton({ onPick }: { onPick: (c: string) => void }) {
  type EyeDropperCtor = new () => { open: () => Promise<{ sRGBHex: string }> }
  const ctor =
    typeof window !== 'undefined'
      ? ((window as unknown as { EyeDropper?: EyeDropperCtor }).EyeDropper ??
        null)
      : null
  if (!ctor) return null
  return (
    <button
      type="button"
      aria-label="Pick colour from screen"
      title="Pick colour from screen"
      onClick={async () => {
        try {
          const result = await new ctor().open()
          if (result?.sRGBHex) onPick(result.sRGBHex)
        } catch {
          /* user dismissed picker; treat as no-op */
        }
      }}
      className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-300 text-sm hover:border-slate-500 dark:border-slate-700"
    >
      <span aria-hidden>⌖</span>
    </button>
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

/** Returns the id of the single selected element when it's a
 *  convertible shape (rect / ellipse / diamond), else ``null``. The
 *  Convert picker is intentionally a single-element affordance —
 *  bulk conversions across mixed types invite surprise. */
function singleConvertibleId(
  store: ElementStore,
  ids: ReadonlySet<string>,
): string | null {
  if (ids.size !== 1) return null
  const [id] = ids
  const el = store.get(id) as { type?: string } | undefined
  if (!el) return null
  if (el.type !== 'rect' && el.type !== 'ellipse' && el.type !== 'diamond') {
    return null
  }
  return id
}

/** ``roundness`` only exists on rect + diamond, so we can't use the
 *  ``BaseElement``-typed ``sharedField`` helper. Returns ``null`` if
 *  no selected element supports the field, the shared numeric value
 *  if all roundness-bearing elements agree, or ``'mixed'`` otherwise. */
function sharedRoundness(
  store: ElementStore,
  ids: ReadonlySet<string>,
): SharedValue<number> {
  let value: number | undefined
  let initialised = false
  for (const id of ids) {
    const el = store.get(id) as { roundness?: number } | undefined
    if (!el || typeof el.roundness !== 'number') continue
    if (!initialised) {
      value = el.roundness
      initialised = true
      continue
    }
    if (el.roundness !== value) return 'mixed'
  }
  return initialised ? (value as number) : null
}

/** Same shape as ``sharedRoundness`` for fields that only exist on
 *  text + sticky elements (``fontFamily``, ``fontSize``, ``textAlign``).
 *  Returns ``null`` when no text-bearing element is in the selection
 *  so the panel can hide the whole text section. */
function sharedTextField<T>(
  store: ElementStore,
  ids: ReadonlySet<string>,
  key: 'fontFamily' | 'fontSize' | 'textAlign',
): SharedValue<T> {
  let value: T | undefined
  let initialised = false
  for (const id of ids) {
    const el = store.get(id) as unknown as
      | { type?: string; [k: string]: unknown }
      | undefined
    if (!el) continue
    if (el.type !== 'text' && el.type !== 'sticky') continue
    const v = el[key] as T | undefined
    if (v === undefined) continue
    if (!initialised) {
      value = v
      initialised = true
      continue
    }
    if (v !== value) return 'mixed'
  }
  return initialised ? (value as T) : null
}

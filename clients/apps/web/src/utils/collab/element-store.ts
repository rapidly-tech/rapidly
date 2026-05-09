/**
 * Thin façade over the shared Yjs Y.Map that holds every whiteboard
 * element. Gives tools and the renderer a typed API without leaking
 * Yjs primitives into every call-site.
 *
 * Shared state shape
 * ------------------
 * ``doc.getMap<Y.Map<unknown>>("elements")`` — root map keyed by
 * ``CollabElement.id``. Each value is itself a ``Y.Map`` holding the
 * element's fields. One-level-deep Y.Map-in-Y.Map so concurrent edits
 * to different fields of the same element merge cleanly, and every
 * change is a first-class Yjs update that rides the E2EE envelope.
 *
 * Local origin tag
 * ----------------
 * Every mutation originated from *this* client is tagged with
 * ``ORIGIN_LOCAL``. The UndoManager we set up later will track only
 * transactions with that origin, so remote edits don't pollute the
 * local undo stack.
 */

import { nanoid } from 'nanoid'
import * as Y from 'yjs'

import {
  DEFAULT_FILL_COLOR,
  DEFAULT_FILL_STYLE,
  DEFAULT_OPACITY,
  DEFAULT_ROUGHNESS,
  DEFAULT_STROKE_COLOR,
  DEFAULT_STROKE_STYLE,
  DEFAULT_STROKE_WIDTH,
  isCollabElement,
  paintOrder,
  type BaseElement,
  type CollabElement,
  type ElementType,
} from './elements'

/** Root key of the element map on the shared doc. Changing this is a
 *  breaking schema migration — don't. */
export const ELEMENTS_KEY = 'elements'

/** Origin marker on every local Yjs transaction so the UndoManager
 *  scoped to this client ignores updates from other peers. Exported so
 *  higher layers (tools, UndoManager setup) can reuse the same symbol. */
export const ORIGIN_LOCAL = Symbol('collab.v2.local')

/** Fields that must be present on every element. Any Y.Map without
 *  them is considered corrupt and skipped on read. */
const REQUIRED_FIELDS: readonly (keyof BaseElement)[] = [
  'id',
  'type',
  'x',
  'y',
  'width',
  'height',
  'angle',
  'zIndex',
  'groupIds',
  'strokeColor',
  'fillColor',
  'fillStyle',
  'strokeWidth',
  'strokeStyle',
  'roughness',
  'opacity',
  'seed',
  'version',
  'locked',
]

/** Caller must supply at least ``{type, x, y, width, height}``; every
 *  other BaseElement field is optional and filled with a default. The
 *  index signature lets tools pass per-type extras (e.g. ``roundness``
 *  on a rect, ``points`` on an arrow) without the store enforcing the
 *  discriminated union — that check belongs in the tool that builds
 *  the element. */
export type CreateElementInput = Partial<BaseElement> &
  Pick<BaseElement, 'type' | 'x' | 'y' | 'width' | 'height'> & {
    [key: string]: unknown
  }

export class ElementStore {
  private readonly root: Y.Map<Y.Map<unknown>>

  constructor(private readonly doc: Y.Doc) {
    this.root = doc.getMap<Y.Map<unknown>>(ELEMENTS_KEY)
  }

  /** Number of elements currently in the shared map. */
  get size(): number {
    return this.root.size
  }

  /** Snapshot the element with ``id`` as a plain object. Returns
   *  ``null`` if the id isn't present or the stored Y.Map fails
   *  validation (likely from a malformed peer).
   *
   *  Reading is cheap — the underlying Y.Map keeps field values in a
   *  flat store — but callers should prefer ``list()`` for bulk reads
   *  to avoid one observe per element in the renderer. */
  get(id: string): CollabElement | null {
    const yEl = this.root.get(id)
    if (!yEl) return null
    return this.materialise(yEl)
  }

  /** Paint-ready list, sorted low-zIndex-first. */
  list(): CollabElement[] {
    const out: CollabElement[] = []
    this.root.forEach((yEl) => {
      const el = this.materialise(yEl)
      if (el) out.push(el)
    })
    out.sort(paintOrder)
    return out
  }

  /** Materialise a single Y.Map entry into a plain object. Validates
   *  the result with ``isCollabElement`` so callers can trust the type. */
  private materialise(yEl: Y.Map<unknown>): CollabElement | null {
    const obj: Record<string, unknown> = {}
    yEl.forEach((value, key) => {
      obj[key] = value
    })
    for (const f of REQUIRED_FIELDS) {
      if (!(f in obj)) return null
    }
    return isCollabElement(obj) ? obj : null
  }

  /** Create a new element with defaults filled in. The caller passes
   *  at minimum ``{type, x, y, width, height}`` plus any per-type
   *  fields; everything else gets a sensible default.
   *
   *  Writes happen in a local-origin transaction so Undo tracks it.
   *  Returns the assigned id. */
  create(input: CreateElementInput): string {
    const id: string = typeof input.id === 'string' ? input.id : nanoid(12)
    const maxZ = this.currentMaxZIndex()

    const baseDefaults: Omit<BaseElement, 'id' | 'type' | 'width' | 'height'> =
      {
        x: 0,
        y: 0,
        angle: 0,
        zIndex: maxZ + 1,
        groupIds: [],
        strokeColor: DEFAULT_STROKE_COLOR,
        fillColor: DEFAULT_FILL_COLOR,
        fillStyle: DEFAULT_FILL_STYLE,
        strokeWidth: DEFAULT_STROKE_WIDTH,
        strokeStyle: DEFAULT_STROKE_STYLE,
        roughness: DEFAULT_ROUGHNESS,
        opacity: DEFAULT_OPACITY,
        seed: Math.floor(Math.random() * 2 ** 31),
        version: 1,
        locked: false,
      }

    const merged: Record<string, unknown> = {
      ...baseDefaults,
      ...input,
      id,
    }

    this.doc.transact(() => {
      const yEl = new Y.Map<unknown>()
      for (const [k, v] of Object.entries(merged)) {
        yEl.set(k, v)
      }
      this.root.set(id, yEl)
    }, ORIGIN_LOCAL)

    return id
  }

  /** Mutate one or more fields of an existing element. No-op if the
   *  id doesn't exist. Bumps ``version`` for cache invalidation. */
  update(
    id: string,
    patch: Partial<BaseElement> & Record<string, unknown>,
  ): void {
    const yEl = this.root.get(id)
    if (!yEl) return
    this.doc.transact(() => {
      for (const [k, v] of Object.entries(patch)) {
        yEl.set(k, v)
      }
      const prevVersion = yEl.get('version')
      yEl.set(
        'version',
        (typeof prevVersion === 'number' ? prevVersion : 0) + 1,
      )
    }, ORIGIN_LOCAL)
  }

  /** Mutate many elements in a single transaction so remote peers see
   *  an atomic frame (e.g. dragging a multi-selection). */
  updateMany(
    patches: readonly {
      id: string
      patch: Partial<BaseElement> & Record<string, unknown>
    }[],
  ): void {
    this.doc.transact(() => {
      for (const { id, patch } of patches) {
        const yEl = this.root.get(id)
        if (!yEl) continue
        for (const [k, v] of Object.entries(patch)) {
          yEl.set(k, v)
        }
        const prevVersion = yEl.get('version')
        yEl.set(
          'version',
          (typeof prevVersion === 'number' ? prevVersion : 0) + 1,
        )
      }
    }, ORIGIN_LOCAL)
  }

  /** Remove an element. Idempotent. Cascade-deletion of bound text,
   *  arrow bindings, and frame children is not automatic — callers
   *  compose the full set of deletes into one transaction via
   *  ``deleteMany`` to keep the remote view atomic. */
  delete(id: string): void {
    if (!this.root.has(id)) return
    this.doc.transact(() => {
      this.root.delete(id)
    }, ORIGIN_LOCAL)
  }

  deleteMany(ids: readonly string[]): void {
    this.doc.transact(() => {
      for (const id of ids) {
        this.root.delete(id)
      }
    }, ORIGIN_LOCAL)
  }

  /** Subscribe to changes. ``fn`` is called whenever any element is
   *  added, removed, or a field changes. The returned disposer
   *  unsubscribes. The renderer typically debounces with rAF before
   *  repainting. */
  observe(fn: (event: Y.YMapEvent<Y.Map<unknown>>) => void): () => void {
    this.root.observe(fn)
    return () => this.root.unobserve(fn)
  }

  /** Deeper observe that also fires for mutations inside per-element
   *  Y.Maps. Necessary for the renderer; not all callers need it. */
  observeDeep(
    fn: (events: Y.YEvent<Y.AbstractType<unknown>>[]) => void,
  ): () => void {
    this.root.observeDeep(fn)
    return () => this.root.unobserveDeep(fn)
  }

  /** The largest zIndex currently in use. Used when creating a new
   *  element so it lands on top. Iterates once — fine for whiteboards
   *  up to a few thousand elements. */
  private currentMaxZIndex(): number {
    let max = -1
    this.root.forEach((yEl) => {
      const z = yEl.get('zIndex')
      if (typeof z === 'number' && z > max) max = z
    })
    return max
  }

  /** Renumber zIndex contiguously from 0. Called after operations that
   *  could create duplicate zIndices (concurrent reorder from two
   *  peers). Idempotent. */
  normaliseZOrder(): void {
    const ordered = this.list()
    this.doc.transact(() => {
      ordered.forEach((el, i) => {
        const yEl = this.root.get(el.id)
        if (yEl) yEl.set('zIndex', i)
      })
    }, ORIGIN_LOCAL)
  }

  /** Utility used in tests and migrations — does the element exist? */
  has(id: string): boolean {
    return this.root.has(id)
  }

  /** Tiny helper so callers don't have to know the key convention if
   *  they need to run code in a local-origin transaction alongside the
   *  store's own mutations. */
  transact(fn: () => void): void {
    this.doc.transact(fn, ORIGIN_LOCAL)
  }

  /** Raw root — used by the UndoManager setup to scope to element
   *  changes only. Not for general consumption. */
  getRoot(): Y.Map<Y.Map<unknown>> {
    return this.root
  }
}

/** Factory helper used in tests + by ``useCollabRoom`` once Phase 1
 *  wires it in. */
export function createElementStore(doc: Y.Doc): ElementStore {
  return new ElementStore(doc)
}

/** Utility type for tools that emit a discriminated-union element on
 *  create. Narrows what's required vs. what the store fills in. */
export type NewElement<T extends ElementType, E extends CollabElement> = Omit<
  Extract<E, { type: T }>,
  keyof Omit<
    BaseElement,
    'type' | 'x' | 'y' | 'width' | 'height' | 'strokeColor' | 'fillColor'
  >
> & { type: T }

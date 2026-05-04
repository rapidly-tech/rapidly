'use client'

/**
 * DOM-overlay that renders a sandboxed iframe for every ``EmbedElement``
 * in the store. Phase 19's iframe layer.
 *
 * Why this lives outside the canvas
 * ---------------------------------
 * The canvas can't run iframes — they're DOM elements. The overlay
 * floats above the canvas in a stacking context that matches the
 * interactive canvas's bounding box. Each iframe is positioned in
 * screen-space from its element's world coords.
 *
 * Click model
 * -----------
 * iframes get ``pointer-events: none`` so canvas pointer-down still
 * works for selection / move / delete / etc. The user can see the
 * embed (a rich YouTube / Loom / Figma / Vimeo preview) but interaction
 * with the embed itself happens in a new tab — Cmd+click on the embed
 * (which Phase 17 already wires for any element with a ``link``) opens
 * the URL. A future ""edit embed"" mode can flip pointer-events back on
 * for the focused embed; not in this PR.
 *
 * Position updates
 * ----------------
 * Pan + zoom don't always trigger a React re-render in the parent
 * (zoom snaps to 0.01 fixed-point), so we run a per-RAF loop here that
 * reads the live viewport from the renderer and sets ``transform`` on
 * each iframe. Cheap: at most one matrix per embed per frame.
 */

import { useEffect, useMemo, useRef, useState } from 'react'

import type { ElementStore } from '@/utils/collab/element-store'
import type { EmbedElement } from '@/utils/collab/elements'
import { isEmbed } from '@/utils/collab/elements'
import {
  EMBED_SANDBOX,
  embedUrlFor,
  isEmbeddableUrl,
} from '@/utils/collab/embed-allowlist'
import type { Renderer } from '@/utils/collab/renderer'

interface Props {
  store: ElementStore
  renderer: Renderer
}

export function EmbedsOverlay({ store, renderer }: Props) {
  // List of embed elements to mount. Re-derived only on store events
  // so unrelated edits don't re-mount the iframes (which would cause
  // every YouTube player to re-load).
  const [embeds, setEmbeds] = useState<EmbedElement[]>(() =>
    store
      .list()
      .filter(isEmbed)
      .map((el) => ({ ...el })),
  )

  useEffect(() => {
    const update = () => {
      setEmbeds(
        store
          .list()
          .filter(isEmbed)
          .map((el) => ({ ...el })),
      )
    }
    return store.observe(update)
  }, [store])

  // Per-RAF position update. Reads viewport + element bbox, writes
  // ``transform`` on the iframe's wrapper div. We don't re-create
  // refs across renders so the iframe DOM stays stable.
  const wrapperRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  useEffect(() => {
    let handle = 0
    const tick = () => {
      const vp = renderer.getViewport()
      for (const el of embeds) {
        const node = wrapperRefs.current.get(el.id)
        if (!node) continue
        const screenX = (el.x - vp.scrollX) * vp.scale
        const screenY = (el.y - vp.scrollY) * vp.scale
        const w = el.width * vp.scale
        const h = el.height * vp.scale
        node.style.transform = `translate(${screenX}px, ${screenY}px)`
        node.style.width = `${w}px`
        node.style.height = `${h}px`
        node.style.display = w > 0 && h > 0 ? 'block' : 'none'
      }
      handle = requestAnimationFrame(tick)
    }
    handle = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(handle)
  }, [embeds, renderer])

  // Memoise the rendered list so React doesn't re-mount iframes on
  // every store-tick. Keyed by id so a peer's create / delete is
  // surgical.
  const rendered = useMemo(() => embeds, [embeds])

  if (rendered.length === 0) return null

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {rendered.map((el) => (
        <div
          key={el.id}
          ref={(node) => {
            if (node) wrapperRefs.current.set(el.id, node)
            else wrapperRefs.current.delete(el.id)
          }}
          className="absolute top-0 left-0 origin-top-left"
        >
          {isEmbeddableUrl(el.url) ? (
            <iframe
              src={embedUrlFor(el.url) ?? el.url}
              sandbox={el.sandbox || EMBED_SANDBOX}
              loading="lazy"
              referrerPolicy="no-referrer"
              allow="autoplay; encrypted-media; picture-in-picture"
              className="h-full w-full border-0"
              title={el.url}
            />
          ) : null}
        </div>
      ))}
    </div>
  )
}

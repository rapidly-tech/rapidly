'use client'

import { FILE_SHARING_API } from '@/utils/file-sharing/constants'
import { useCallback, useEffect, useRef, useState } from 'react'

// Inlined ``solar:share-linear`` SVG so the icon paints on first
// render rather than chasing a runtime fetch from
// ``api.iconify.design`` (visible delay on phones with cold caches).
function ShareIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="24"
      height="24"
      className={className}
      aria-hidden="true"
    >
      <g fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M9 12a2.5 2.5 0 1 1-5 0a2.5 2.5 0 0 1 5 0Z" />
        <path strokeLinecap="round" d="M14 6.5L9 10m5 7.5L9 14" />
        <path d="M19 18.5a2.5 2.5 0 1 1-5 0a2.5 2.5 0 0 1 5 0Zm0-13a2.5 2.5 0 1 1-5 0a2.5 2.5 0 0 1 5 0Z" />
      </g>
    </svg>
  )
}

const POLL_INTERVAL = 30_000 // 30s

/** Dispatch this event from anywhere on the page to trigger an immediate counter refresh. */
export const SHARE_CREATED_EVENT = 'rapidly:share-created'

/**
 * When `workspaceId` is provided, shows workspace-scoped session count
 * from the authenticated API. Otherwise falls back to the public global
 * stats endpoint (used on the public landing page).
 */
export const ShareCounter = ({
  workspaceId,
  initialCount,
}: {
  workspaceId?: string
  /** Server-rendered count for the public landing — when supplied
   *  the counter paints the live number on first render with no
   *  waiting for a client-side fetch. The poll + share-created
   *  listener still run on top so in-session updates animate. */
  initialCount?: number
}) => {
  // ── Combined count (sessions + secrets) via /stats endpoint ──
  const [count, setCount] = useState<number | null>(
    typeof initialCount === 'number' ? initialCount : null,
  )
  const hasFetched = useRef(false)

  const fetchCount = useCallback(async () => {
    try {
      const url = workspaceId
        ? `${FILE_SHARING_API}/stats?workspace_id=${workspaceId}`
        : `${FILE_SHARING_API}/stats`
      // ``cache: 'no-store'`` so the share-created event always sees
      // a live number — without it the browser HTTP cache may serve
      // a stale response from the previous poll, making new shares
      // appear "after some time" instead of immediately.
      const res = await fetch(url, { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        setCount(data.total_shares)
      }
    } catch {
      // Silently ignore — counter is cosmetic
    }
  }, [workspaceId])

  useEffect(() => {
    if (!hasFetched.current) {
      hasFetched.current = true
      // Skip the first fetch when the server already gave us a
      // count — we trust the SSR value until the next poll tick
      // refreshes it. Saves a redundant network round-trip on
      // first paint.
      if (typeof initialCount !== 'number') {
        fetchCount()
      }
    }
    const id = setInterval(fetchCount, POLL_INTERVAL)

    // Optimistic +1 on share-created so the number ticks visibly the
    // instant the user finishes the share — the network round-trip
    // for ``/stats`` (request + cache-miss recompute + response) was
    // adding ~300-700 ms of dead air before the digit changed, which
    // the user perceived as "doesn't update immediately". The
    // following ``fetchCount`` reconciles to the authoritative value
    // a moment later; if the optimistic and real values match (the
    // common case), there's no second visual change.
    const onShareCreated = () => {
      setCount((c) => (typeof c === 'number' ? c + 1 : c))
      fetchCount()
    }
    window.addEventListener(SHARE_CREATED_EVENT, onShareCreated)

    return () => {
      clearInterval(id)
      window.removeEventListener(SHARE_CREATED_EVENT, onShareCreated)
    }
  }, [fetchCount, initialCount])

  // Reserve the slot's vertical space via ``min-h`` so the landing
  // layout doesn't reflow when the number arrives. ``count === 0``
  // keeps the slot reserved but empty — nothing to brag about yet,
  // and reflowing later if the first share lands during the visit
  // would be jarring.
  const ready = count !== null && count > 0
  return (
    <div
      className="flex min-h-[3.25rem] flex-col items-center gap-1"
      aria-hidden={!ready}
    >
      {ready ? (
        <>
          {/* Render the value directly — no spring, no easing.
              Any tween puts a perceptible beat between ``setCount``
              and the digit changing; for single-digit deltas on a
              small number, a clean snap reads as more responsive. */}
          <span className="text-lg font-semibold tracking-tight text-slate-500 tabular-nums dark:text-slate-400">
            {count.toLocaleString('en-US')}
          </span>
          <div className="flex items-center gap-x-1.5">
            <ShareIcon className="h-3 w-3 text-slate-400 dark:text-slate-500" />
            <span className="rp-text-muted text-xs font-medium">
              shares so far
            </span>
          </div>
        </>
      ) : null}
    </div>
  )
}

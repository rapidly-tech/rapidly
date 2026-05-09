'use client'

import { CONFIG } from '@/utils/config'
import { useCallback, useEffect, useRef, useState } from 'react'

// Hit the backend directly. ``CONFIG.BASE_URL`` is the API origin
// (``https://api.rapidly.tech`` in prod, ``http://127.0.0.1:8000`` in
// dev) — not the frontend origin. On prod the same-origin
// ``/api/file-sharing/stats`` is ~990 ms because it pays a full
// rewrite hop through the Next.js server before reaching the backend;
// the direct request lands in ~230 ms.
//
// CORS on the backend already allows ``https://rapidly.tech`` with
// credentials, and the auth cookie is scoped to ``.rapidly.tech`` so
// it crosses to the api subdomain — the workspace-membership check
// from #613 still fires.
//
// (Earlier #619 reverted #617's direct-URL move based on a misread
// of the bundle: the template literal looked unresolved, but
// ``CONFIG.BASE_URL`` *does* resolve to the api subdomain at runtime.
// Verified by inspecting the config chunk.)
const STATS_URL = `${CONFIG.BASE_URL}/api/file-sharing/stats`

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
 * (requires the caller to be a member of that workspace). Otherwise
 * falls back to the public global stats endpoint.
 */
export const ShareCounter = ({ workspaceId }: { workspaceId?: string }) => {
  const [count, setCount] = useState<number | null>(null)
  // Mirror of ``count`` for use inside the share-created listener
  // without binding the listener to ``count`` (which would re-attach
  // it on every change and risk dropping in-flight events).
  const countRef = useRef<number | null>(null)
  countRef.current = count

  const fetchCount = useCallback(async () => {
    try {
      const url = workspaceId
        ? `${STATS_URL}?workspace_id=${workspaceId}`
        : STATS_URL
      // ``credentials: 'include'`` so the auth cookie crosses subdomains
      // for the workspace-scoped path (otherwise #613's membership check
      // would 401 logged-in users on the dashboard).
      const res = await fetch(url, {
        cache: 'no-store',
        credentials: 'include',
      })
      if (res.ok) {
        const data = await res.json()
        setCount(data.total_shares)
      }
    } catch {
      // cosmetic — silently ignore
    }
  }, [workspaceId])

  useEffect(() => {
    fetchCount()
    const id = setInterval(fetchCount, POLL_INTERVAL)

    // Source of truth for the user's own action: bump optimistically
    // and DON'T re-fetch immediately. The earlier "optimistic + then
    // fetchCount()" version raced — if the fetch returned the value
    // from before the increment had propagated through whatever cache
    // sat between the client and Redis, ``setCount(stale)`` clobbered
    // the optimistic +1 and the user saw the digit revert until the
    // 30 s poll. Trusting the optimistic update means the digit moves
    // immediately and stays moved; the next poll handles drift.
    //
    // Edge case: if ``count`` is still null when the listener fires
    // (the user shared before the first fetch resolved), the +1 is a
    // no-op — fall back to fetching so the counter still appears.
    const onShareCreated = () => {
      if (typeof countRef.current === 'number') {
        setCount((c) => (typeof c === 'number' ? c + 1 : c))
      } else {
        fetchCount()
      }
    }
    window.addEventListener(SHARE_CREATED_EVENT, onShareCreated)

    // Re-fetch on foreground return. Mobile's Web Share API suspends
    // the page while the OS share sheet is open; in-flight fetches
    // and the poll are paused. Triggering a fetch on resume catches
    // anything the suspend window dropped.
    const onVisible = () => {
      if (document.visibilityState === 'visible') fetchCount()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      clearInterval(id)
      window.removeEventListener(SHARE_CREATED_EVENT, onShareCreated)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [fetchCount])

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

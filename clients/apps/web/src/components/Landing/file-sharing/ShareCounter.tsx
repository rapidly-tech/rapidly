'use client'

import { FILE_SHARING_API } from '@/utils/file-sharing/constants'
import { motion, useSpring, useTransform } from 'framer-motion'
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
export const ShareCounter = ({ workspaceId }: { workspaceId?: string }) => {
  // ── Combined count (sessions + secrets) via /stats endpoint ──
  const [count, setCount] = useState<number | null>(null)
  const hasFetched = useRef(false)

  const fetchCount = useCallback(async () => {
    try {
      const url = workspaceId
        ? `${FILE_SHARING_API}/stats?workspace_id=${workspaceId}`
        : `${FILE_SHARING_API}/stats`
      const res = await fetch(url)
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
      fetchCount()
    }
    const id = setInterval(fetchCount, POLL_INTERVAL)

    const onShareCreated = () => fetchCount()
    window.addEventListener(SHARE_CREATED_EVENT, onShareCreated)

    return () => {
      clearInterval(id)
      window.removeEventListener(SHARE_CREATED_EVENT, onShareCreated)
    }
  }, [fetchCount])

  // Reserve the slot's vertical space before the fetch resolves so
  // landing layout doesn't reflow when the number arrives. We still
  // hide the contents (``opacity-0`` + ``aria-hidden``) until we
  // have a real number, so screen readers don't announce "0".
  // ``count === 0`` keeps the slot reserved but invisible — there's
  // genuinely nothing to brag about, but reflowing later if the
  // first share lands during the visit would be jarring.
  const ready = count !== null && count > 0
  return (
    <div
      className={
        'flex flex-col items-center gap-1 transition-opacity duration-300 ' +
        (ready ? 'opacity-100' : 'opacity-0')
      }
      aria-hidden={!ready}
    >
      <span className="text-lg font-semibold tracking-tight text-slate-500 tabular-nums dark:text-slate-400">
        <AnimatedNumber value={count ?? 0} />
      </span>
      <div className="flex items-center gap-x-1.5">
        <ShareIcon className="h-3 w-3 text-slate-400 dark:text-slate-500" />
        <span className="rp-text-muted text-xs font-medium">shares so far</span>
      </div>
    </div>
  )
}

const AnimatedNumber = ({ value }: { value: number }) => {
  const prevRef = useRef(value)
  const spring = useSpring(value, { stiffness: 80, damping: 20, mass: 0.5 })
  const display = useTransform(spring, (v) =>
    Math.round(v).toLocaleString('en-US'),
  )

  useEffect(() => {
    if (prevRef.current !== value) {
      prevRef.current = value
      spring.set(value)
    }
  }, [spring, value])

  return <motion.span>{display}</motion.span>
}

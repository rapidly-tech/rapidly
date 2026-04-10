'use client'

import { FILE_SHARING_API } from '@/utils/file-sharing/constants'
import { Icon } from '@iconify/react'
import { motion, useSpring, useTransform } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'

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

  if (count === null || count === 0) return null

  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-lg font-semibold tracking-tight text-slate-500 tabular-nums dark:text-slate-400">
        <AnimatedNumber value={count} />
      </span>
      <div className="flex items-center gap-x-1.5">
        <Icon
          icon="solar:share-linear"
          className="h-3 w-3 text-slate-400 dark:text-slate-500"
        />
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

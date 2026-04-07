import { FILE_SHARING_API } from '@/utils/file-sharing/constants'
import { logger } from '@/utils/file-sharing/logger'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

/** Creates and manages a file-sharing uploader channel with automatic renewal and cleanup. */
export function useUploaderChannel(
  maxDownloads = 0,
  renewInterval = 60_000,
  pricing?: {
    priceCents?: number | null
    currency?: string
    title?: string
    fileName?: string
    fileSizeBytes?: number
    workspaceId?: string
  },
): {
  isLoading: boolean
  error: Error | null
  shortSlug: string | undefined
  secret: string | undefined
} {
  const priceCents = pricing?.priceCents
  const currency = pricing?.currency
  const title = pricing?.title
  const fileName = pricing?.fileName
  const fileSizeBytes = pricing?.fileSizeBytes
  const workspaceId = pricing?.workspaceId

  // Unique ID per component mount — guarantees a fresh channel every time.
  // useState with initializer runs once per mount, unlike useId which is
  // tied to tree position and can return the same value on remount.
  const [instanceId] = useState(() => crypto.randomUUID())

  const { isLoading, error, data } = useQuery({
    queryKey: ['uploaderChannel', instanceId],
    queryFn: async () => {
      logger.log('[UploaderChannel] creating new channel')
      const body: Record<string, unknown> = { max_downloads: maxDownloads }
      if (priceCents && priceCents > 0) {
        body.price_cents = priceCents
        body.currency = currency || 'usd'
      }
      if (title) body.title = title
      if (fileName) body.file_name = fileName
      if (fileSizeBytes) body.file_size_bytes = fileSizeBytes
      if (workspaceId) body.workspace_id = workspaceId
      const response = await fetch(`${FILE_SHARING_API}/channels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        logger.error(
          '[UploaderChannel] failed to create channel:',
          response.status,
        )
        throw new Error('Network response was not ok')
      }
      const data = await response.json()
      logger.log('[UploaderChannel] channel created successfully:', {
        short_slug: data.short_slug,
      })
      // Notify the share counter to refresh immediately
      window.dispatchEvent(new Event('rapidly:share-created'))
      return data
    },
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    refetchOnReconnect: false,
    staleTime: Infinity,
  })

  const secret = data?.secret
  const shortSlug = data?.short_slug

  // Ref to avoid stale shortSlug closure in the mutation function
  const shortSlugRef = useRef(shortSlug)
  shortSlugRef.current = shortSlug

  // ── Channel renewal ──

  const renewMutation = useMutation({
    mutationFn: async ({ secret: s }: { secret: string }) => {
      const slug = shortSlugRef.current
      logger.log('[UploaderChannel] renewing channel for slug', slug)
      const response = await fetch(
        `${FILE_SHARING_API}/channels/${slug}/renew`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ secret: s }),
        },
      )
      if (!response.ok) {
        logger.error(
          '[UploaderChannel] failed to renew channel',
          response.status,
        )
        throw new Error('Network response was not ok')
      }
      const data = await response.json()
      logger.log('[UploaderChannel] channel renewed successfully')
      return data
    },
  })

  // Stable ref for mutate function to avoid useEffect re-triggering on every mutation
  const renewRef = useRef(renewMutation.mutate)
  renewRef.current = renewMutation.mutate

  const stableRenew = useCallback(
    (args: { secret: string }) => renewRef.current(args),
    [],
  )

  // ── Auto-renewal timer ──

  useEffect(() => {
    if (!secret || !shortSlug) return

    const id = setInterval(() => {
      logger.log(
        '[UploaderChannel] renewing channel, interval',
        renewInterval,
        'ms',
      )
      stableRenew({ secret })
    }, renewInterval)

    return () => {
      logger.log('[UploaderChannel] clearing renewal interval')
      clearInterval(id)
    }
  }, [secret, shortSlug, stableRenew, renewInterval])

  // ── Cleanup on unload ──

  useEffect(() => {
    if (!shortSlug || !secret) return

    const handleUnload = (): void => {
      logger.log('[UploaderChannel] destroying channel on page unload')
      // Use Blob with JSON content type so FastAPI can parse the body
      const blob = new Blob([JSON.stringify({ secret })], {
        type: 'application/json',
      })
      navigator.sendBeacon(
        `${FILE_SHARING_API}/channels/${shortSlug}/destroy`,
        blob,
      )
    }

    window.addEventListener('beforeunload', handleUnload)

    return () => {
      window.removeEventListener('beforeunload', handleUnload)
    }
  }, [shortSlug, secret])

  return {
    isLoading,
    error,
    shortSlug,
    secret,
  }
}

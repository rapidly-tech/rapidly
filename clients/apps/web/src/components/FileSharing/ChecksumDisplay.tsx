'use client'

import { FILE_SHARING_API } from '@/utils/file-sharing/constants'
import { deriveReaderToken } from '@/utils/file-sharing/encryption'
import { logger } from '@/utils/file-sharing/logger'
import { JSX, useEffect, useRef, useState } from 'react'

interface ChecksumDisplayProps {
  slug: string
  encryptionKey: CryptoKey | null
  hkdfSalt?: Uint8Array
}

/**
 * Displays per-file SHA-256 checksums fetched from the server.
 *
 * Shown on the download-complete page so users can independently verify
 * downloaded file integrity with `sha256sum` or similar tools.
 */
export function ChecksumDisplay({
  slug,
  encryptionKey,
  hkdfSalt,
}: ChecksumDisplayProps): JSX.Element | null {
  const [checksums, setChecksums] = useState<Record<string, string> | null>(
    null,
  )
  const [copiedFile, setCopiedFile] = useState<string | null>(null)
  // Track copy timeout so it can be cleared on unmount (prevents state update on unmounted component)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!slug || !encryptionKey || !hkdfSalt) return
    let cancelled = false

    const fetchChecksums = async () => {
      try {
        const token = await deriveReaderToken(encryptionKey, hkdfSalt)
        const resp = await fetch(
          `${FILE_SHARING_API}/channels/${slug}/checksums`,
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        )
        if (!cancelled && resp.ok) {
          const data = await resp.json()
          if (data.checksums && Object.keys(data.checksums).length > 0) {
            setChecksums(data.checksums)
          }
        }
      } catch (err) {
        logger.warn('[ChecksumDisplay] failed to fetch checksums:', err)
      }
    }

    fetchChecksums()
    return () => {
      cancelled = true
    }
  }, [slug, encryptionKey, hkdfSalt])

  // Clean up copy timer on unmount
  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    }
  }, [])

  const copyChecksum = async (fileName: string, hash: string) => {
    try {
      await navigator.clipboard.writeText(hash)
      setCopiedFile(fileName)
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
      copyTimerRef.current = setTimeout(() => setCopiedFile(null), 2000)
    } catch {
      // Clipboard API unavailable in some contexts (e.g. non-HTTPS)
    }
  }

  if (!checksums) return null

  return (
    <div className="w-full rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h4 className="mb-3 text-sm font-medium text-slate-700 dark:text-slate-300">
        SHA-256 Checksums
      </h4>
      <div className="space-y-2">
        {Object.entries(checksums).map(([fileName, hash]) => (
          <div key={fileName} className="group">
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">
              {fileName}
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 font-mono text-xs break-all text-slate-600 select-all dark:text-slate-300">
                {hash}
              </code>
              <button
                type="button"
                onClick={() => copyChecksum(fileName, hash)}
                className="shrink-0 rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                aria-label={`Copy checksum for ${fileName}`}
              >
                {copiedFile === fileName ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

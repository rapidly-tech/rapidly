import {
  CLIPBOARD_CLEAR_DELAY_MS,
  DEBOUNCE_DELAY_MS,
} from '@/utils/constants/timings'
import { logger } from '@/utils/file-sharing/logger'
import { useCallback, useEffect, useRef, useState } from 'react'

/** Copies text to the clipboard with automatic clear and fallback for older browsers. */
export default function useClipboard(
  text: string,
  delay = DEBOUNCE_DELAY_MS,
): {
  hasCopied: boolean
  onCopy: () => void
} {
  const [hasCopied, setHasCopied] = useState(false)
  const clearTimerRef = useRef<NodeJS.Timeout | null>(null)

  const scheduleClear = useCallback(() => {
    if (clearTimerRef.current) clearTimeout(clearTimerRef.current)
    clearTimerRef.current = setTimeout(() => {
      navigator.clipboard?.writeText('').catch(() => {}) // Clipboard may be unavailable
    }, CLIPBOARD_CLEAR_DELAY_MS)
  }, [])

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (clearTimerRef.current) clearTimeout(clearTimerRef.current)
    }
  }, [])

  const onCopy = useCallback(() => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(() => {
          setHasCopied(true)
          scheduleClear()
        })
        .catch((error) => {
          logger.error('Clipboard API error:', error)
          fallbackCopyText(text)
        })
    } else {
      fallbackCopyText(text)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, scheduleClear])

  const fallbackCopyText = (textToCopy: string) => {
    const textArea = document.createElement('textarea')
    textArea.value = textToCopy

    textArea.style.position = 'absolute'
    textArea.style.left = '-999999px'

    document.body.appendChild(textArea)
    textArea.select()

    try {
      document.execCommand('copy')
      setHasCopied(true)
      scheduleClear()
    } catch (error) {
      logger.error('execCommand:', error)
    } finally {
      textArea.remove()
    }
  }

  useEffect(() => {
    let timeoutId: NodeJS.Timeout
    if (hasCopied) {
      timeoutId = setTimeout(() => {
        setHasCopied(false)
      }, delay)
    }
    return () => {
      clearTimeout(timeoutId)
    }
  }, [hasCopied, delay])

  return { hasCopied, onCopy }
}

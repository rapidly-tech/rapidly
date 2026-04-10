import { useCallback, useEffect, useRef, useState } from 'react'

export type URLValidationStatus = 'idle' | 'validating' | 'valid' | 'invalid'

interface ValidationState {
  status: URLValidationStatus
  error?: string
}

const INITIAL_STATE: ValidationState = { status: 'idle' }

/** Validates a URL by sending it to the server, with caching and abort support. */
export function useURLValidation({ workspaceSlug }: { workspaceSlug: string }) {
  const [state, setState] = useState<ValidationState>(INITIAL_STATE)
  const cache = useRef(new Map<string, ValidationState>())
  const controller = useRef<AbortController | null>(null)

  // Abort in-flight request on unmount
  useEffect(() => () => controller.current?.abort(), [])

  const validateURL = useCallback(
    async (url: string) => {
      const trimmed = url?.trim()
      if (
        !trimmed ||
        (!trimmed.startsWith('https://') && !trimmed.startsWith('http://'))
      ) {
        setState(INITIAL_STATE)
        return
      }

      const hit = cache.current.get(trimmed)
      if (hit) {
        setState(hit)
        return
      }

      controller.current?.abort()
      controller.current = new AbortController()
      setState({ status: 'validating' })

      try {
        const res = await fetch(
          `/dashboard/${workspaceSlug}/settings/validate-website`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: trimmed }),
            signal: controller.current.signal,
          },
        )
        const body = await res.json()
        const result: ValidationState = {
          status: body.reachable ? 'valid' : 'invalid',
          error: body.error,
        }
        cache.current.set(trimmed, result)
        setState(result)
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') return
        setState({ status: 'invalid', error: 'Failed to validate URL' })
      }
    },
    [workspaceSlug],
  )

  const reset = useCallback(() => {
    controller.current?.abort()
    setState(INITIAL_STATE)
  }, [])

  return { status: state.status, error: state.error, validateURL, reset }
}

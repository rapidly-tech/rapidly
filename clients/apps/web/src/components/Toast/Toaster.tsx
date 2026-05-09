'use client'

import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { useCallback, useEffect } from 'react'
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from '.'
import { useToast } from './use-toast'

// Search param keys that trigger and configure redirect-based toasts
const TOAST_TRIGGER_KEY = 'toast'
const REDIRECT_TOAST_PARAMS = [
  TOAST_TRIGGER_KEY,
  'error',
  'status',
  'status_description',
  'error_description',
] as const

function stripToastParams(raw: URLSearchParams): URLSearchParams {
  const cleaned = new URLSearchParams(raw.toString())
  for (const key of REDIRECT_TOAST_PARAMS) {
    cleaned.delete(key)
  }
  return cleaned
}

function ToastItem({
  id,
  title,
  description,
  action,
  ...rest
}: {
  id: string
  title?: React.ReactNode
  description?: React.ReactNode
  action?: React.ReactNode
  [key: string]: unknown
}) {
  return (
    <Toast key={id} {...rest}>
      <div className="flex w-full flex-col gap-1">
        <ToastClose />
        <div className="rounded-xl bg-white px-5 py-4 dark:bg-white/5">
          <div className="grid gap-1">
            {title ? <ToastTitle>{title}</ToastTitle> : null}
            {description ? (
              <ToastDescription>{description}</ToastDescription>
            ) : null}
          </div>
          {action}
        </div>
      </div>
    </Toast>
  )
}

export function Toaster() {
  const { toast, toasts } = useToast()
  const params = useSearchParams()
  const path = usePathname()
  const router = useRouter()

  const handleRedirectToast = useCallback(() => {
    if (params.get(TOAST_TRIGGER_KEY) !== 'true') return

    const errorMsg = params.get('error')
    const statusMsg = params.get('status')
    if (!errorMsg && !statusMsg) return

    const isError = Boolean(errorMsg)
    toast({
      title: isError
        ? (errorMsg ?? 'Hmm... Something went wrong.')
        : (statusMsg ?? 'Alright!'),
      description: isError
        ? params.get('error_description')
        : params.get('status_description'),
      variant: isError ? 'error' : undefined,
      duration: 3000,
    })

    const remaining = stripToastParams(new URLSearchParams(params.toString()))
    router.replace(`${path}?${remaining.toString()}`, { scroll: false })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])

  useEffect(handleRedirectToast, [handleRedirectToast])

  return (
    <ToastProvider>
      {toasts.map((entry) => (
        <ToastItem key={entry.id} {...entry} />
      ))}
      <ToastViewport />
    </ToastProvider>
  )
}

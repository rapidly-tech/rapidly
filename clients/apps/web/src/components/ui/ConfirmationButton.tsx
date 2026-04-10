'use client'

import Button from '@rapidly-tech/ui/components/forms/Button'
import React, { useCallback, useEffect, useState } from 'react'

interface ConfirmationButtonProps {
  onConfirm: () => void
  warningMessage: string
  buttonText: string
  confirmText: string
  disabled?: boolean
  loading?: boolean
  variant?:
    | 'default'
    | 'secondary'
    | 'destructive'
    | 'outline'
    | 'ghost'
    | 'link'
  size?: 'default' | 'sm' | 'lg' | 'icon'
  className?: string
  requireConfirmation?: boolean
  destructive?: boolean
}

// Visual presets for the confirmation state
const CONFIRM_THEME = {
  normal: {
    icon: 'text-slate-600 dark:text-slate-400',
    label: 'text-slate-800 dark:text-slate-200',
  },
  danger: {
    icon: 'text-red-500 dark:text-red-400',
    label: 'text-red-800 dark:text-red-200',
  },
} as const

const WarningTriangle = () => (
  <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
    <path
      fillRule="evenodd"
      d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
      clipRule="evenodd"
    />
  </svg>
)

export default function ConfirmationButton({
  onConfirm,
  warningMessage,
  buttonText,
  confirmText,
  disabled = false,
  loading = false,
  variant = 'default',
  size = 'default',
  className = '',
  requireConfirmation = true,
  destructive = false,
}: ConfirmationButtonProps) {
  const [awaitingConfirm, setAwaitingConfirm] = useState(false)

  const resetConfirm = useCallback(() => setAwaitingConfirm(false), [])

  // Dismiss confirmation state on Escape
  useEffect(() => {
    if (!awaitingConfirm) return

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') resetConfirm()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [awaitingConfirm, resetConfirm])

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()

    if (requireConfirmation && !disabled) {
      setAwaitingConfirm(true)
    } else {
      onConfirm()
    }
  }

  // Initial (idle) state
  if (!awaitingConfirm) {
    return (
      <Button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        loading={loading}
        variant={variant}
        size={size}
        className={className}
      >
        {buttonText}
      </Button>
    )
  }

  // Confirmation state
  const theme = destructive ? CONFIRM_THEME.danger : CONFIRM_THEME.normal

  return (
    <div className="flex flex-col gap-3 sm:gap-4">
      <div
        className={`flex items-center gap-2 text-sm ${theme.label} font-medium sm:flex-1`}
      >
        <div className={theme.icon}>
          <WarningTriangle />
        </div>
        <span>{warningMessage}</span>
      </div>

      <div className="flex gap-2 sm:shrink-0">
        <Button
          type="button"
          onClick={() => {
            onConfirm()
            resetConfirm()
          }}
          loading={loading}
          size={size}
          variant={destructive ? 'destructive' : 'default'}
          autoFocus
          className="flex-1 sm:flex-initial"
        >
          {confirmText}
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={resetConfirm}
          disabled={loading}
          size={size}
          className="flex-1 sm:flex-initial"
        >
          Cancel
        </Button>
      </div>
    </div>
  )
}

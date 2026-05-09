'use client'

import { Icon } from '@iconify/react'
import { useState } from 'react'
import { twMerge } from 'tailwind-merge'
import Button from './Button'
import Input from './Input'

const CopyToClipboardInput = ({
  value,
  onCopy,
  buttonLabel,
  disabled = false,
  className = '',
}: {
  value: string
  onCopy?: () => void
  buttonLabel?: string
  disabled?: boolean
  className?: string
}) => {
  const [isCopied, setIsCopied] = useState(false)

  const copyToClipboard = () => {
    navigator.clipboard.writeText(value).catch(() => {
      // Clipboard API may be unavailable (e.g. permissions denied, insecure context)
    })

    if (onCopy) {
      onCopy()
    }

    setIsCopied(true)

    setTimeout(() => {
      setIsCopied(false)
    }, 2000)
  }

  return (
    <div
      className={twMerge(
        'flex w-full flex-row items-center overflow-hidden rounded-2xl border border-white/8 bg-white/4 shadow-sm backdrop-blur-2xl backdrop-saturate-150 dark:border-white/6 dark:bg-white/3',
        className,
      )}
    >
      <Input
        className="!focus:border-transparent !focus:ring-transparent !dark:focus:border-transparent !dark:focus:ring-transparent w-full grow border-none bg-transparent text-slate-600 shadow-none! focus-visible:ring-transparent dark:bg-transparent dark:text-slate-400 dark:focus-visible:ring-transparent"
        value={value}
        readOnly={true}
      />
      {!disabled && (
        <Button
          className="mr-1 text-xs"
          type="button"
          size="sm"
          variant="ghost"
          onClick={copyToClipboard}
        >
          {isCopied ? (
            <Icon icon="solar:check-read-linear" className="text-sm" />
          ) : (
            buttonLabel || 'Copy'
          )}
        </Button>
      )}
    </div>
  )
}

export default CopyToClipboardInput

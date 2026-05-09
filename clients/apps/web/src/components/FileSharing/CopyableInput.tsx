'use client'

import useClipboard from '@/hooks/file-sharing/useClipboard'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import { JSX, useId } from 'react'
import InputLabel from './InputLabel'

export function CopyableInput({
  label,
  value,
}: {
  label: string
  value: string
}): JSX.Element {
  const { hasCopied, onCopy } = useClipboard(value)
  const inputId = useId()

  return (
    <div className="flex w-full flex-col">
      <InputLabel htmlFor={inputId}>{label}</InputLabel>
      <div className="flex w-full">
        <Input
          id={inputId}
          className="grow rounded-r-none border-r-0"
          value={value}
          readOnly
        />
        <Button
          type="button"
          variant="secondary"
          size="default"
          className="rounded-l-none"
          onClick={onCopy}
          aria-label={`Copy ${label}`}
        >
          {hasCopied ? 'Copied!' : 'Copy'}
        </Button>
      </div>
    </div>
  )
}

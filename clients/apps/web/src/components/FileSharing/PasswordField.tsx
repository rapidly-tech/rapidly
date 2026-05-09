'use client'

import Input from '@rapidly-tech/ui/components/forms/Input'
import React, { JSX, useCallback, useId } from 'react'
import { twMerge } from 'tailwind-merge'
import InputLabel from './InputLabel'

export default function PasswordField({
  value,
  onChange,
  isRequired = false,
  isInvalid = false,
  autoFocus: shouldAutoFocus = false,
}: {
  value: string
  onChange: (v: string) => void
  isRequired?: boolean
  isInvalid?: boolean
  autoFocus?: boolean
}): JSX.Element {
  const inputId = useId()
  const handleChange = useCallback(
    function (e: React.ChangeEvent<HTMLInputElement>): void {
      onChange(e.target.value)
    },
    [onChange],
  )

  return (
    <div className="flex w-full flex-col">
      <InputLabel
        htmlFor={inputId}
        hasError={isInvalid}
        tooltip="The downloader must provide this password to start downloading the file. If you don't specify a password here, any downloader with the link to the file will be able to download it."
      >
        {isRequired ? 'Password' : 'Password (optional)'}
      </InputLabel>
      <Input
        id={inputId}
        autoFocus={shouldAutoFocus}
        type="password"
        aria-invalid={isInvalid || undefined}
        className={twMerge(isInvalid && 'border-red-500 dark:border-red-400')}
        placeholder="Enter a password to protect this file..."
        value={value}
        onChange={handleChange}
      />
    </div>
  )
}

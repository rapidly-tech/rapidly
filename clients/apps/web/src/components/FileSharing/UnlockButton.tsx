'use client'

import Button from '@rapidly-tech/ui/components/forms/Button'
import React, { JSX } from 'react'

export default function UnlockButton({
  onClick,
}: {
  onClick?: React.MouseEventHandler<HTMLButtonElement>
}): JSX.Element {
  return (
    <Button
      type="submit"
      variant="secondary"
      size="lg"
      className="w-full"
      onClick={onClick}
    >
      <svg
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z"
        />
      </svg>
      Unlock
    </Button>
  )
}

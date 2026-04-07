'use client'

import Button from '@rapidly-tech/ui/components/forms/Button'
import type { MouseEventHandler, ReactElement } from 'react'

export default function StopButton({
  isDownloading,
  onClick,
}: {
  onClick: MouseEventHandler<HTMLButtonElement>
  isDownloading?: boolean
}): ReactElement {
  return (
    <Button type="button" variant="destructive" size="sm" onClick={onClick}>
      <svg
        className="h-4 w-4"
        viewBox="0 0 24 24"
        fill="currentColor"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <rect x="6" y="6" width="12" height="12" rx="2" />
      </svg>
      {isDownloading ? 'Stop Download' : 'Stop Sharing'}
    </Button>
  )
}

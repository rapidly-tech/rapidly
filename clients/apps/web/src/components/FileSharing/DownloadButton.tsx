'use client'

import Button from '@rapidly-tech/ui/components/forms/Button'
import React, { JSX } from 'react'
import { DownloadIcon } from './Icons'

export default function DownloadButton({
  onClick,
}: {
  onClick?: React.MouseEventHandler
}): JSX.Element {
  return (
    <Button
      type="button"
      variant="secondary"
      size="lg"
      className="w-full"
      id="download-button"
      onClick={onClick}
    >
      <DownloadIcon />
      Download
    </Button>
  )
}

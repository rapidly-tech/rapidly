'use client'

import Button from '@rapidly-tech/ui/components/forms/Button'
import type { MouseEventHandler, ReactElement } from 'react'

export default function StartButton({
  onClick,
}: {
  onClick?: MouseEventHandler<HTMLButtonElement>
}): ReactElement {
  return (
    <Button
      type={onClick ? 'button' : 'submit'}
      variant="secondary"
      size="lg"
      className="w-full"
      onClick={onClick}
    >
      Start Sharing
    </Button>
  )
}

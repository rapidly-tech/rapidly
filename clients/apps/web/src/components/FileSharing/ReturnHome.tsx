'use client'

import Button from '@rapidly-tech/ui/components/forms/Button'
import { JSX, useCallback } from 'react'

export default function ReturnHome(): JSX.Element {
  const handleClick = useCallback(() => {
    // Hard navigation to clear hash fragment and file sharing state
    window.location.href = '/'
  }, [])

  return (
    <div className="mt-4 flex justify-center">
      <Button variant="ghost" onClick={handleClick}>
        Share more files &raquo;
      </Button>
    </div>
  )
}

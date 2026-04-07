'use client'

import React, { JSX } from 'react'

export default function TitleText({
  children,
}: {
  children: React.ReactNode
}): JSX.Element {
  return (
    <h2 className="mb-4 text-center text-3xl font-semibold tracking-tight md:text-5xl">
      {children}
    </h2>
  )
}

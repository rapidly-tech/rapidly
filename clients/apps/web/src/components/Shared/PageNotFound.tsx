'use client'

import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'

/** Renders a full-screen 404 page with a link to return home. */
const PageNotFound = () => {
  return (
    <div className="flex h-screen w-full flex-col items-center justify-center gap-y-16 px-12">
      <h1 className="text-4xl text-slate-600 dark:text-slate-400">404</h1>
      <h1 className="max-w-xl text-center text-4xl leading-normal">
        We couldn&apos;t find the page you were looking for
      </h1>
      <Link href={`/`}>
        <Button>Take me home</Button>
      </Link>
    </div>
  )
}

export default PageNotFound

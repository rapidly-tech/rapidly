import Link from 'next/link'
import { Children, PropsWithChildren, ReactNode } from 'react'
import { twMerge } from 'tailwind-merge'

// Documentation building blocks, content-compatible with the page
// bodies imported from the previous docs platform. All visuals follow
// the design system (slate surfaces, emerald accents, lg radii).

export const Card = ({
  title,
  href,
  children,
}: PropsWithChildren<{ title: string; icon?: string; href?: string }>) => {
  const className =
    'docs-card flex flex-col gap-1 rounded-lg border border-slate-200 bg-white p-4 no-underline dark:border-slate-800 dark:bg-slate-900'
  const body = (
    <>
      <span className="font-medium text-slate-900 dark:text-white">
        {title}
      </span>
      <span className="text-sm text-slate-500 dark:text-slate-400">
        {children}
      </span>
    </>
  )
  if (href) {
    return (
      <Link
        href={href}
        className={twMerge(
          className,
          'transition-colors hover:border-emerald-300 dark:hover:border-emerald-800',
        )}
      >
        {body}
      </Link>
    )
  }
  return <div className={className}>{body}</div>
}

export const CardGroup = ({
  cols = 2,
  children,
}: PropsWithChildren<{ cols?: number }>) => (
  <div
    className={twMerge(
      'my-4 grid grid-cols-1 gap-3',
      cols >= 3 ? 'md:grid-cols-3' : 'md:grid-cols-2',
    )}
  >
    {children}
  </div>
)

export const Steps = ({ children }: PropsWithChildren) => (
  <div className="docs-steps my-4 flex flex-col gap-0">{children}</div>
)

export const Step = ({
  title,
  children,
}: PropsWithChildren<{ title?: string; icon?: string }>) => (
  <div className="relative flex gap-4 pb-6 last:pb-0">
    <div className="flex flex-col items-center">
      <span className="docs-step-marker mt-0.5 size-2 shrink-0 rounded-full bg-emerald-500" />
      <span className="w-px grow bg-slate-200 dark:bg-slate-800" />
    </div>
    <div className="min-w-0">
      {title && (
        <p className="mt-0! mb-2 font-medium text-slate-900 dark:text-white">
          {title}
        </p>
      )}
      <div className="text-sm">{children}</div>
    </div>
  </div>
)

export const AccordionGroup = ({ children }: PropsWithChildren) => (
  <div className="my-4 flex flex-col gap-2">{children}</div>
)

export const Accordion = ({
  title,
  children,
}: PropsWithChildren<{ title: string; icon?: string }>) => (
  <details className="group rounded-lg border border-slate-200 dark:border-slate-800">
    <summary className="cursor-pointer px-4 py-3 font-medium text-slate-900 select-none dark:text-white">
      {title}
    </summary>
    <div className="border-t border-slate-200 px-4 py-3 dark:border-slate-800">
      {children}
    </div>
  </details>
)

export const CodeGroup = ({ children }: PropsWithChildren) => (
  <div className="docs-code-group my-4 flex flex-col gap-2">
    {Children.toArray(children)}
  </div>
)

export const ParamField = ({
  path,
  query,
  header: headerName,
  body,
  type,
  required,
  children,
}: PropsWithChildren<{
  path?: string
  query?: string
  header?: string
  body?: string
  type?: string
  required?: boolean
}>) => {
  const name = path ?? query ?? headerName ?? body ?? ''
  return (
    <div className="my-3 border-b border-slate-100 pb-3 dark:border-slate-800">
      <div className="flex flex-wrap items-baseline gap-2 font-mono text-sm">
        <span className="font-medium text-slate-900 dark:text-white">
          {name}
        </span>
        {type && (
          <span className="text-slate-500 dark:text-slate-400">{type}</span>
        )}
        {required && (
          <span className="text-xs text-amber-600 dark:text-amber-400">
            required
          </span>
        )}
      </div>
      <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        {children}
      </div>
    </div>
  )
}

export const Frame = ({
  caption,
  children,
}: PropsWithChildren<{ caption?: ReactNode }>) => (
  <figure className="my-4 overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
    {children}
    {caption && (
      <figcaption className="border-t border-slate-200 px-4 py-2 text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
        {caption}
      </figcaption>
    )}
  </figure>
)

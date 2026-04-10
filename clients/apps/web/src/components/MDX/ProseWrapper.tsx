import { PropsWithChildren } from 'react'
import { twMerge } from 'tailwind-merge'

/** Wraps content with consistent prose typography styles for MDX-rendered content. */
const ProseWrapper = ({
  children,
  className,
}: PropsWithChildren<{ className?: string }>) => {
  return (
    <div
      className={twMerge(
        className,
        'prose dark:prose-invert prose-p:text-lg rp-text-primary',
        'prose-p:tracking-normal prose-p:leading-relaxed prose-hr:border-slate-300 dark:prose-hr:border-slate-700',
        'prose-img:rounded-lg prose-img:shadow-xs prose-img:border prose-img:border-slate-200 dark:prose-img:border-slate-900',
        'prose-headings:rp-text-primary prose-h1:text-5xl prose-h2:text-3xl prose-h3:text-2xl prose-h4:text-xl prose-h5:text-lg prose-h6:text-md prose-headings:font-semibold prose-headings:tracking-tight',
        'prose-a:text-slate-600 dark:prose-a:text-slate-400 prose-a:no-underline prose-a:font-normal',
        'prose-pre:whitespace-pre-wrap dark:prose-pre:bg-slate-900 dark:prose-pre:border-slate-800 prose-pre:border prose-pre:border-transparent prose-pre:bg-slate-100 prose-pre:rounded-2xl prose-pre:text-slate-600 dark:prose-pre:text-slate-400',
        'prose-code:before:content-none prose-code:after:content-none prose-code:bg-slate-100 dark:prose-code:bg-slate-900 prose-code:font-normal prose-code:rounded-xs prose-code:px-1.5 prose-code:py-1',
      )}
    >
      {children}
    </div>
  )
}

export default ProseWrapper

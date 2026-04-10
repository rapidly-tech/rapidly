import { DetailedHTMLProps } from 'react'
import { twMerge } from 'tailwind-merge'

const ResponsivePanel = ({
  className,
  children,
  ...props
}: DetailedHTMLProps<React.HTMLAttributes<HTMLDivElement>, HTMLDivElement>) => (
  <div
    className={twMerge(
      'w-full md:rounded-2xl md:border md:border-white/[0.08] md:bg-white/[0.04] md:p-8 md:backdrop-blur-2xl md:backdrop-saturate-150 lg:rounded-4xl dark:md:border-white/[0.06] dark:md:bg-white/[0.03]',
      className,
    )}
    {...props}
  >
    {children}
  </div>
)

export default ResponsivePanel

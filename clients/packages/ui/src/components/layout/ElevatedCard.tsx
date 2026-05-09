import { PropsWithChildren } from 'react'
import { twMerge } from 'tailwind-merge'
import ResponsivePanel from '../overlay/ResponsivePanel'

/** Card with elevated styling, subtle background, and border for visual emphasis. */
const ElevatedCard = ({
  ref,
  ...props
}: PropsWithChildren<{ className?: string }> & {
  ref?: React.RefObject<HTMLDivElement>
}) => (
  <div
    ref={ref}
    className={twMerge(
      'glass-elevated w-full rounded-2xl p-8 lg:rounded-3xl',
      props.className,
    )}
  >
    {props.children}
  </div>
)

ElevatedCard.displayName = 'ElevatedCard'

export default ElevatedCard

export { ResponsivePanel }

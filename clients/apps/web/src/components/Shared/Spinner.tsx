import { twMerge } from 'tailwind-merge'

// SVG arc data shared between both spinner variants
const TRACK_CIRCLE = { cx: 12, cy: 12, r: 10, strokeWidth: 4 } as const
const ARC_PATH =
  'M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z'

function SpinnerSVG({ className }: { className: string }) {
  return (
    <svg
      className={twMerge('animate-spin', className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" stroke="currentColor" {...TRACK_CIRCLE} />
      <path className="opacity-75" fill="currentColor" d={ARC_PATH} />
    </svg>
  )
}

const Spinner = () => <SpinnerSVG className="mr-3 -ml-1 h-5 w-5" />

export default Spinner

export const SpinnerNoMargin = ({
  className = 'h-5 w-5',
}: {
  className?: string
}) => <SpinnerSVG className={className} />

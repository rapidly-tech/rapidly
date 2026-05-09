import { Input as ShadInput } from '@/components/primitives/input'
import { type ComponentProps, type ReactNode } from 'react'
import { twMerge } from 'tailwind-merge'

/** Props extending the base input primitive with leading/trailing adornments. */
export type InputProps = ComponentProps<typeof ShadInput> & {
  preSlot?: ReactNode
  postSlot?: ReactNode
}

const BASE_CLASSES = [
  'h-10 rounded-2xl border px-3 py-2 text-base shadow-sm outline-none transition-all duration-200 md:text-sm',
  'border-(--beige-border)/30 bg-white text-foreground placeholder:text-slate-400',
  'focus:z-10 focus:border-(--beige-focus)/60 focus:ring-[3px] focus:ring-(--beige-border)/20 focus-visible:ring-(--beige-border)/20 focus:shadow-md',
  'dark:border-white/[0.06] dark:bg-white/[0.03] dark:placeholder:text-slate-500',
  'dark:ring-offset-transparent dark:focus:border-slate-500/30 dark:focus:ring-slate-600/20 dark:focus:bg-(--beige-item-hover)',
].join(' ')

function buildAdornment(content: ReactNode, side: 'left' | 'right') {
  const positioning = side === 'left' ? 'left-0 pl-3' : 'right-0 pr-4'
  return (
    <span
      className={twMerge(
        'pointer-events-none absolute inset-y-0 z-10 flex items-center text-slate-500 dark:text-slate-400',
        positioning,
      )}
    >
      {content}
    </span>
  )
}

/** Text input with optional leading and trailing adornment slots. */
const Input = ({ ref, preSlot, postSlot, className, ...rest }: InputProps) => {
  const paddingAdjust = twMerge(
    BASE_CLASSES,
    preSlot ? 'pl-10' : '',
    postSlot ? 'pr-10' : '',
    className,
  )

  return (
    <div className="relative flex flex-1 flex-row rounded-full">
      <ShadInput className={paddingAdjust} ref={ref} {...rest} />
      {preSlot ? buildAdornment(preSlot, 'left') : null}
      {postSlot ? buildAdornment(postSlot, 'right') : null}
    </div>
  )
}

Input.displayName = 'Input'

export default Input

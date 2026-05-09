import { Textarea } from '@/components/primitives/textarea'
import { twMerge } from 'tailwind-merge'

/** Props for the TextArea component, with an optional resizable flag. */
export interface TextAreaProps extends React.ComponentProps<'textarea'> {
  resizable?: boolean | undefined
}

/** Multi-line text input with theme-aware styling and optional resize control. */
const TextArea = ({
  ref,
  resizable = true,
  className,
  ...props
}: TextAreaProps) => {
  const classNames = twMerge(
    'border-(--beige-border)/30 bg-white shadow-sm dark:border-white/[0.06] dark:bg-white/[0.03] dark:placeholder:text-slate-500 min-h-[120px] rounded-2xl p-4 text-sm outline-none transition-all duration-200 focus:z-10 focus:border-(--beige-focus)/60 focus:ring-[3px] focus:ring-(--beige-border)/20 focus:shadow-md dark:ring-offset-transparent dark:focus:border-slate-500/30 dark:focus:ring-slate-600/20 dark:focus:bg-(--beige-item-hover)',
    resizable ? '' : 'resize-none',
    className,
  )

  return <Textarea ref={ref} className={classNames} {...props} />
}

TextArea.displayName = 'TextArea'

export default TextArea

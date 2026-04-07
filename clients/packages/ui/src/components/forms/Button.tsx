import {
  ButtonProps,
  Button as ShadcnButton,
} from '@/components/primitives/button'
import { cva } from 'class-variance-authority'
import React from 'react'
import { twMerge } from 'tailwind-merge'

// Variant-driven styling for all button appearances
const btnStyles = cva(
  'relative inline-flex cursor-pointer select-none items-center justify-center whitespace-nowrap rounded-2xl text-sm font-medium ring-offset-background transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.97]',
  {
    variants: {
      variant: {
        default:
          'bg-slate-700/80 backdrop-blur-2xl backdrop-saturate-150 border border-white/[0.15] text-white shadow-md hover:bg-slate-700/90 hover:shadow-lg hover:shadow-slate-500/25 hover:scale-[1.02]',
        destructive:
          'bg-red-500/80 backdrop-blur-2xl backdrop-saturate-150 border border-white/[0.1] text-white shadow-md hover:bg-red-500/90 hover:scale-[1.02] dark:bg-red-600/80 dark:hover:bg-red-600/90',
        outline:
          'border border-(--beige-border)/30 bg-white text-foreground shadow-sm hover:bg-slate-50 hover:scale-[1.02] dark:border-white/[0.06] dark:bg-white/[0.03] dark:hover:bg-(--beige-item-hover)',
        secondary:
          'border border-(--beige-border)/30 bg-white text-foreground shadow-sm hover:bg-slate-50 hover:scale-[1.02] dark:border-white/[0.06] dark:bg-white/[0.04] dark:hover:bg-(--beige-item-hover)',
        underline:
          'rounded-none! border-b border-transparent bg-transparent p-0! text-foreground transition-colors duration-300 hover:border-foreground hover:bg-transparent active:scale-100!',
        link: 'bg-transparent text-slate-500 underline-offset-4 hover:bg-transparent hover:underline active:scale-100!',
        ghost:
          'bg-transparent text-foreground hover:bg-(--beige-item-hover) hover:scale-[1.02] dark:bg-transparent dark:hover:bg-(--beige-item-hover)',
        teal: 'border border-white/[0.15] bg-teal-500/80 backdrop-blur-2xl backdrop-saturate-150 text-white shadow-md hover:bg-teal-500/90 hover:shadow-lg hover:shadow-teal-500/25 hover:scale-[1.02] dark:bg-teal-600/80 dark:hover:bg-teal-600/90',
      },
      size: {
        default: 'h-10 rounded-2xl px-4 py-2 text-sm',
        sm: 'h-8 rounded-xl px-3 py-1.5 text-xs',
        lg: 'h-12 rounded-2xl px-5 py-4 text-sm',
        icon: 'flex h-8 w-8 items-center justify-center rounded-xl p-2 text-sm',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

// Circular spinner rendered inside a button during loading state
function Spinner({
  isDisabled,
  btnSize,
}: {
  isDisabled?: boolean
  btnSize: ButtonProps['size']
}) {
  const dimension =
    btnSize === 'default' || btnSize === 'lg' ? 'h-4 w-4' : 'h-2 w-2'
  const coloring = isDisabled
    ? 'fill-white text-white/20'
    : 'fill-white text-slate-300'

  return (
    <div role="status">
      <svg
        aria-hidden="true"
        className={twMerge('animate-spin', dimension, coloring)}
        viewBox="0 0 100 101"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
          fill="currentColor"
        />
        <path
          d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
          fill="currentFill"
        />
      </svg>
    </div>
  )
}

/** Themed button with variant styles, loading spinner overlay, and full-width mode. */
const Button = ({
  ref,
  className,
  wrapperClassNames,
  variant,
  size,
  loading,
  fullWidth,
  disabled,
  children,
  type = 'button',
  ...rest
}: ButtonProps & {
  ref?: React.RefObject<HTMLButtonElement>
  wrapperClassNames?: string
  loading?: boolean
  fullWidth?: boolean
}) => {
  const resolvedClasses = twMerge(
    btnStyles({ variant, size, className }),
    fullWidth && 'w-full',
  )
  const isDisabled = disabled || loading

  return (
    <ShadcnButton
      className={resolvedClasses}
      ref={ref}
      disabled={isDisabled}
      type={type}
      aria-busy={loading ?? undefined}
      {...rest}
    >
      {loading ? (
        <>
          <span className="absolute inset-0 flex h-full w-full items-center justify-center">
            <Spinner isDisabled={disabled} btnSize={size} />
          </span>
          <span className="flex flex-row items-center opacity-0">
            {children}
          </span>
        </>
      ) : (
        <span
          className={twMerge('flex flex-row items-center', wrapperClassNames)}
        >
          {children}
        </span>
      )}
    </ShadcnButton>
  )
}

Button.displayName = ShadcnButton.displayName

export default Button

/** Bare button wrapper applying variant classes without loading or full-width support. */
export const RawButton = ({
  ref,
  className,
  variant,
  size,
  children,
  ...rest
}: ButtonProps & {
  ref?: React.RefObject<HTMLButtonElement>
}) => (
  <ShadcnButton
    className={twMerge(btnStyles({ variant, size, className }))}
    ref={ref}
    {...rest}
  >
    {children}
  </ShadcnButton>
)

RawButton.displayName = 'RawButton'

export type { ButtonProps }

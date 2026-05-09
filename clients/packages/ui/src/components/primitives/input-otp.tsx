'use client'

import { Icon } from '@iconify/react'
import { OTPInput, OTPInputContext, RenderProps } from 'input-otp'
import * as React from 'react'

import { cn } from '@/lib/utils'

const InputOTP = ({
  ref,
  className,
  containerClassName,
  ...props
}: React.ComponentProps<typeof OTPInput>) => (
  <OTPInput
    ref={ref}
    containerClassName={cn(
      'flex items-center gap-2 has-disabled:opacity-50',
      containerClassName,
    )}
    className={cn('disabled:cursor-not-allowed', className)}
    {...props}
  />
)
InputOTP.displayName = 'InputOTP'

const InputOTPGroup = ({
  ref,
  className,
  ...props
}: React.ComponentProps<'div'>) => (
  <div ref={ref} className={cn('flex items-center', className)} {...props} />
)
InputOTPGroup.displayName = 'InputOTPGroup'

const InputOTPSlot = ({
  ref,
  index,
  className,
  ...props
}: {
  index: number
  className?: string
} & React.ComponentProps<'div'>) => {
  const inputOTPContext = React.useContext<RenderProps>(OTPInputContext)
  const { char, hasFakeCaret, isActive } = inputOTPContext.slots[index]

  return (
    <div
      ref={ref}
      className={cn(
        'relative flex h-10 w-10 items-center justify-center border-y border-r border-white/[0.08] bg-white/[0.04] text-sm backdrop-blur-2xl backdrop-saturate-150 transition-all first:rounded-l-xl first:border-l last:rounded-r-xl dark:border-white/[0.06] dark:bg-white/[0.03]',
        isActive && 'ring-ring ring-offset-background z-10 ring-2',
        className,
      )}
      {...props}
    >
      {char}
      {hasFakeCaret && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="animate-caret-blink bg-foreground h-4 w-px duration-1000" />
        </div>
      )}
    </div>
  )
}
InputOTPSlot.displayName = 'InputOTPSlot'

const InputOTPSeparator = ({ ref, ...props }: React.ComponentProps<'div'>) => (
  <div ref={ref} role="separator" {...props}>
    <Icon icon="solar:record-circle-linear" />
  </div>
)
InputOTPSeparator.displayName = 'InputOTPSeparator'

export { InputOTP, InputOTPGroup, InputOTPSeparator, InputOTPSlot }

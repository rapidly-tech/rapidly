'use client'

import * as SwitchPrimitives from '@radix-ui/react-switch'
import * as React from 'react'
import { twMerge } from 'tailwind-merge'

/** Toggle switch for boolean on/off controls. */
const Switch = ({
  ref,
  className,
  ...props
}: React.ComponentProps<typeof SwitchPrimitives.Root>) => (
  <SwitchPrimitives.Root
    className={twMerge(
      'focus-visible:ring-ring focus-visible:ring-offset-background peer inline-flex h-[18px] w-[37px] shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-all duration-200 focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-slate-600/80 data-[state=checked]:shadow-sm data-[state=checked]:backdrop-blur-2xl data-[state=checked]:backdrop-saturate-150 data-[state=unchecked]:bg-white/[0.06] data-[state=unchecked]:backdrop-blur-2xl data-[state=unchecked]:backdrop-saturate-150 dark:data-[state=unchecked]:bg-white/[0.04]',
      className,
    )}
    {...props}
    ref={ref}
  >
    <SwitchPrimitives.Thumb
      className={twMerge(
        'pointer-events-none block h-2 w-2 rounded-full bg-white shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-[22px] data-[state=unchecked]:translate-x-1 dark:data-[state=checked]:bg-white dark:data-[state=unchecked]:bg-slate-400',
      )}
    />
  </SwitchPrimitives.Root>
)
Switch.displayName = SwitchPrimitives.Root.displayName

export default Switch

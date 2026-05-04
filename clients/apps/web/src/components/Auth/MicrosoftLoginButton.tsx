'use client'

import { usePostHog, type EventName } from '@/hooks/posthog'
import { getMicrosoftAuthorizeLoginURL } from '@/utils/auth'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'
import { useCallback } from 'react'
import { twMerge } from 'tailwind-merge'

interface MicrosoftLoginButtonProps {
  className?: string
  returnTo?: string
  signup?: schemas['UserSignupAttribution']
  size?: 'large' | 'small'
  fullWidth?: boolean
  text: string
}

/** Redirects the user to the Microsoft OAuth authorization flow. */
const MicrosoftLoginButton = ({
  className,
  returnTo,
  signup,
  size = 'small',
  fullWidth,
  text,
}: MicrosoftLoginButtonProps) => {
  const posthog = usePostHog()

  const authorizeURL = getMicrosoftAuthorizeLoginURL({
    return_to: returnTo,
    attribution: JSON.stringify(signup),
  })

  const handleClick = useCallback(() => {
    const eventName: EventName = signup
      ? 'global:user:signup:submit'
      : 'global:user:login:submit'
    posthog.capture(eventName, { method: 'microsoft' })
  }, [posthog, signup])

  const isLarge = size === 'large'

  return (
    <Link href={authorizeURL} onClick={handleClick}>
      <Button
        wrapperClassNames={twMerge(
          isLarge
            ? 'p-2.5 px-5 text-md space-x-3'
            : 'p-2 px-4 text-sm space-x-2',
          className,
        )}
        className={twMerge(isLarge && 'text-md p-5')}
        fullWidth={fullWidth}
      >
        <svg
          className={twMerge('shrink-0', isLarge ? 'h-5 w-5' : 'h-4 w-4')}
          aria-hidden="true"
          viewBox="0 0 21 21"
          fill="none"
        >
          <rect x="1" y="1" width="9" height="9" fill="#F25022" />
          <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
          <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
          <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
        </svg>
        <span className="whitespace-nowrap">{text}</span>
      </Button>
    </Link>
  )
}

export default MicrosoftLoginButton

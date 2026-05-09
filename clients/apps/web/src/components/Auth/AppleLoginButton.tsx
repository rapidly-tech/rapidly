import { usePostHog, type EventName } from '@/hooks/posthog'
import { getAppleAuthorizeURL } from '@/utils/auth'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'
import { useCallback } from 'react'

interface AppleLoginButtonProps {
  returnTo?: string
  signup?: schemas['UserSignupAttribution']
}

/** Redirects the user to the Apple OAuth authorization flow. */
const AppleLoginButton = ({ returnTo, signup }: AppleLoginButtonProps) => {
  const posthog = usePostHog()

  const authorizeURL = getAppleAuthorizeURL({
    return_to: returnTo,
    attribution: JSON.stringify(signup),
  })

  const handleClick = useCallback(() => {
    const eventName: EventName = signup
      ? 'global:user:signup:submit'
      : 'global:user:login:submit'
    posthog.capture(eventName, { method: 'apple' })
  }, [posthog, signup])

  return (
    <Link href={authorizeURL} onClick={handleClick}>
      <Button
        variant="secondary"
        wrapperClassNames="space-x-3 p-2.5 px-5"
        className="text-md p-5"
        fullWidth
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 814.08 999.04"
          fill="currentColor"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76.5 0-103.7 40.8-165.9 40.8s-105.6-57.8-155.5-127.4c-58.4-81.8-105.9-209.3-105.9-330.8 0-194.3 126.4-297.5 250.8-297.5 66.1 0 121.2 43.4 162.7 43.4 39.5 0 101.1-46 176.3-46 28.5 0 130.9 2.6 198.3 99.2zm-234-181.5c31.1-36.9 53.1-88.1 53.1-139.3 0-7.1-.6-14.3-1.9-20.1-50.6 1.9-110.8 33.7-147.1 75.8-28.5 32.4-55.1 83.6-55.1 135.5 0 7.8.6 15.7 1.3 18.2 2.6.6 6.4 1.3 10.2 1.3 45.4 0 103.5-30.4 139.5-71.4z" />
        </svg>
        <div>Continue with Apple</div>
      </Button>
    </Link>
  )
}

export default AppleLoginButton

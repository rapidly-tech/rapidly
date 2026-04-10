import { schemas } from '@rapidly-tech/client'
import Link from 'next/link'
import LogoIcon from '../Brand/LogoIcon'
import Login from './Login'

interface AuthModalProps {
  returnTo?: string
  returnParams?: Record<string, string>
  signup?: schemas['UserSignupAttribution']
}

/**
 * Full authentication modal content.
 * Shows the Rapidly logo, a contextual headline, and the login / signup form.
 */
export const AuthModal = ({
  returnTo,
  returnParams,
  signup,
}: AuthModalProps) => {
  const isSignup = signup !== undefined
  const heading = isSignup ? 'Sign Up' : 'Log In'

  return (
    <div className="overflow-y-auto p-12">
      <div className="flex flex-col justify-between gap-y-16">
        <Link href="/">
          <LogoIcon className="rp-text-primary" size={60} />
        </Link>

        <div className="flex flex-col gap-y-4">
          <h1 className="text-3xl">{heading}</h1>
          {isSignup && (
            <p className="text-xl text-slate-500 dark:text-slate-400">
              Join thousands of users sharing files securely with Rapidly.
            </p>
          )}
        </div>

        <div className="flex flex-col gap-y-12">
          <Login
            returnTo={returnTo}
            returnParams={returnParams}
            signup={signup}
          />
        </div>
      </div>
    </div>
  )
}

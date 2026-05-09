'use client'

import {
  useAuth,
  useDisconnectOAuthAccount,
  useGoogleAccount,
  useMicrosoftAccount,
} from '@/hooks'
import {
  getGoogleAuthorizeLinkURL,
  getMicrosoftAuthorizeLinkURL,
} from '@/utils/auth'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import ItemGroup from '@rapidly-tech/ui/components/navigation/ItemGroup'
import { usePathname, useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import EmailUpdateForm from '../Form/EmailUpdateForm'

// ---------------------------------------------------------------------------
// Generic auth-method row
// ---------------------------------------------------------------------------

interface AuthMethodRowProps {
  icon: React.ReactNode
  title: React.ReactNode
  subtitle: React.ReactNode
  action: React.ReactNode
}

const AuthMethodRow: React.FC<AuthMethodRowProps> = ({
  icon,
  title,
  subtitle,
  action,
}) => (
  <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-center">
    <div>{icon}</div>
    <div className="grow">
      <div className="font-medium">{title}</div>
      <div className="text-sm text-slate-500 dark:text-slate-400">
        {subtitle}
      </div>
    </div>
    <div>{action}</div>
  </div>
)

// ---------------------------------------------------------------------------
// Provider-specific rows
// ---------------------------------------------------------------------------

interface OAuthMethodProps {
  oauthAccount: schemas['OAuthAccountRead'] | undefined
  returnTo: string
  onDisconnect: () => void
  isDisconnecting: boolean
}

const MicrosoftRow: React.FC<OAuthMethodProps> = ({
  oauthAccount,
  returnTo,
  onDisconnect,
  isDisconnecting,
}) => {
  const authorizeURL = getMicrosoftAuthorizeLinkURL({ return_to: returnTo })

  const displayName = oauthAccount
    ? oauthAccount.account_username
      ? `${oauthAccount.account_username} (${oauthAccount.account_email})`
      : oauthAccount.account_email
    : 'Connect Microsoft'

  return (
    <AuthMethodRow
      icon={<Icon icon="solar:monitor-linear" className="h-5 w-5" />}
      title={displayName}
      subtitle={
        oauthAccount
          ? 'You can sign in with your Microsoft account.'
          : 'Link your Microsoft account for quicker access.'
      }
      action={
        oauthAccount ? (
          <Button
            variant="secondary"
            onClick={onDisconnect}
            loading={isDisconnecting}
          >
            Disconnect
          </Button>
        ) : (
          <Button asChild>
            <a href={authorizeURL}>Connect</a>
          </Button>
        )
      }
    />
  )
}

const GoogleRow: React.FC<OAuthMethodProps> = ({
  oauthAccount,
  returnTo,
  onDisconnect,
  isDisconnecting,
}) => {
  const authorizeURL = getGoogleAuthorizeLinkURL({ return_to: returnTo })

  return (
    <AuthMethodRow
      icon={<Icon icon="solar:monitor-linear" className="h-5 w-5" />}
      title={oauthAccount ? oauthAccount.account_email : 'Connect Google'}
      subtitle={
        oauthAccount
          ? 'You can sign in with your Google account.'
          : 'Link your Google account for faster login.'
      }
      action={
        oauthAccount ? (
          <Button
            variant="secondary"
            onClick={onDisconnect}
            loading={isDisconnecting}
          >
            Disconnect
          </Button>
        ) : (
          <Button asChild>
            <a href={authorizeURL}>Connect</a>
          </Button>
        )
      }
    />
  )
}

// ---------------------------------------------------------------------------
// Main Settings Panel
// ---------------------------------------------------------------------------

/**
 * Authentication settings panel.
 * Shows connected OAuth providers (Microsoft, Google) and the current email
 * address with an inline change-email flow.
 */
const AuthenticationSettings = () => {
  const { currentUser, reloadUser } = useAuth()
  const pathname = usePathname()
  const microsoftAccount = useMicrosoftAccount()
  const googleAccount = useGoogleAccount()
  const disconnectOAuth = useDisconnectOAuthAccount()

  const searchParams = useSearchParams()
  const [emailStage, setEmailStage] = useState<
    'off' | 'form' | 'request' | 'verified'
  >((searchParams.get('update_email') as 'verified' | null) || 'off')
  const [didReload, setDidReload] = useState(false)

  useEffect(() => {
    if (!didReload && emailStage === 'verified') {
      reloadUser()
      setDidReload(true)
    }
  }, [emailStage, reloadUser, didReload])

  const emailActionContent: Record<typeof emailStage, React.ReactNode> = {
    off: currentUser ? (
      <Button onClick={() => setEmailStage('form')}>Change Email</Button>
    ) : null,
    form: (
      <EmailUpdateForm
        onEmailUpdateRequest={() => setEmailStage('request')}
        onCancel={() => setEmailStage('off')}
        returnTo={`${pathname}?update_email=verified`}
      />
    ),
    request: (
      <div className="text-center text-sm text-slate-500 dark:text-slate-300">
        A verification email has been sent to your new address.
      </div>
    ),
    verified: (
      <div className="text-center text-sm text-emerald-700 dark:text-emerald-400">
        Your email has been updated successfully.
      </div>
    ),
  }

  const returnTo = pathname || '/start'

  return (
    <ItemGroup>
      <ItemGroup.Item>
        <MicrosoftRow
          oauthAccount={microsoftAccount}
          returnTo={returnTo}
          onDisconnect={() => disconnectOAuth.mutate('microsoft')}
          isDisconnecting={disconnectOAuth.isPending}
        />
      </ItemGroup.Item>

      <ItemGroup.Item>
        <GoogleRow
          oauthAccount={googleAccount}
          returnTo={returnTo}
          onDisconnect={() => disconnectOAuth.mutate('google')}
          isDisconnecting={disconnectOAuth.isPending}
        />
      </ItemGroup.Item>

      <ItemGroup.Item>
        <AuthMethodRow
          icon={<Icon icon="solar:mention-circle-linear" className="h-5 w-5" />}
          title={currentUser?.email}
          subtitle="Sign in with a one-time code sent to your email"
          action={emailActionContent[emailStage]}
        />
      </ItemGroup.Item>
    </ItemGroup>
  )
}

export default AuthenticationSettings

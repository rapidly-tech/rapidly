import { useWorkspaceAccount } from '@/hooks/api'
import { ACCOUNT_TYPE_DISPLAY_NAMES, ACCOUNT_TYPE_ICON } from '@/utils/account'
import { Icon as IconifyIcon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Banner from '@rapidly-tech/ui/components/feedback/Banner'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'
import { useMemo } from 'react'
import Icon from '../Icons/Icon'

const SetupAction = ({ href }: { href: string }) => (
  <Link href={href}>
    <Button size="sm">Setup</Button>
  </Link>
)

const ContinueSetupAction = ({ href }: { href: string }) => (
  <Link href={href}>
    <Button size="sm">Continue setup</Button>
  </Link>
)

const MissingAccountBanner = ({ setupLink }: { setupLink: string }) => (
  <Banner color="default" right={<SetupAction href={setupLink} />}>
    <IconifyIcon
      icon="solar:danger-circle-linear"
      className="h-6 w-6 text-red-500"
    />
    <span className="text-sm">
      You need to set up a <strong>payout account</strong> to receive payouts
    </span>
  </Banner>
)

const OnboardingBanner = ({
  account,
  setupLink,
}: {
  account: schemas['Account']
  setupLink: string
}) => {
  const AccountTypeIcon = ACCOUNT_TYPE_ICON[account.account_type]
  const displayName = ACCOUNT_TYPE_DISPLAY_NAMES[account.account_type]

  return (
    <Banner color="default" right={<ContinueSetupAction href={setupLink} />}>
      <Icon
        classes="bg-(--surface-bold) text-(--text-inverted) p-1"
        icon={<AccountTypeIcon />}
      />
      <span className="text-sm">
        Continue the setup of your <strong>{displayName}</strong> account to
        receive payouts
      </span>
    </Banner>
  )
}

const GenericAccountBanner = ({
  account,
  setupLink,
}: {
  account: schemas['Account'] | undefined
  setupLink: string
}) => {
  if (!account) return <MissingAccountBanner setupLink={setupLink} />
  if (account.status === 'onboarding_started')
    return <OnboardingBanner account={account} setupLink={setupLink} />
  return null
}

interface AccountBannerProps {
  workspace: schemas['Workspace']
}

const isForbiddenError = (error: unknown): boolean =>
  Boolean(
    error &&
    typeof error === 'object' &&
    'response' in error &&
    (error as { response: { status: number } }).response?.status === 403,
  )

const AccountBanner: React.FC<AccountBannerProps> = ({ workspace }) => {
  const {
    data: workspaceAccount,
    isLoading,
    error: accountError,
  } = useWorkspaceAccount(workspace?.id)

  const setupLink = useMemo(
    () => `/dashboard/${workspace.slug}/finance/account`,
    [workspace.slug],
  )

  if (isLoading) return null
  if (isForbiddenError(accountError)) return null

  return (
    <GenericAccountBanner account={workspaceAccount} setupLink={setupLink} />
  )
}

export default AccountBanner

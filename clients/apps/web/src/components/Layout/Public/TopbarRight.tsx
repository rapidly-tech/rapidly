'use client'

import { AuthModal } from '@/components/Auth/AuthModal'
import GetStartedButton from '@/components/Auth/GetStartedButton'
import { Modal } from '@/components/Modal'
import { useModal } from '@/components/Modal/useModal'
import PublicProfileDropdown from '@/components/Navigation/PublicProfileDropdown'
import Popover from '@/components/Notifications/NotificationsPopover'
import { usePostHog } from '@/hooks/posthog'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { usePathname } from 'next/navigation'
import { useCallback, useMemo } from 'react'

const LOGIN_MODAL_WIDTH = 'lg:w-full lg:max-w-[480px]'

const AuthenticatedView = ({ user }: { user: schemas['UserRead'] }) => (
  <div>
    <div className="relative flex w-max shrink-0 flex-row items-center justify-between gap-x-6">
      <Popover />
      <PublicProfileDropdown authenticatedUser={user} className="shrink-0" />
    </div>
  </div>
)

const TopbarRight = ({
  authenticatedUser,
  storefrontOrg,
}: {
  authenticatedUser?: schemas['UserRead']
  storefrontOrg?: schemas['Workspace']
}) => {
  const posthog = usePostHog()
  const pathname = usePathname()
  const { isShown: isModalShown, hide: hideModal, show: showModal } = useModal()

  const loginReturnTo = useMemo(() => pathname ?? '/start', [pathname])

  const onLoginClick = useCallback(() => {
    posthog.capture('global:user:login:click')
    showModal()
  }, [posthog, showModal])

  if (authenticatedUser) {
    return <AuthenticatedView user={authenticatedUser} />
  }

  return (
    <>
      <Button onClick={onLoginClick} variant="secondary">
        Log in
      </Button>

      <GetStartedButton
        className="hidden md:flex"
        size="default"
        text="Get Started"
        storefrontOrg={storefrontOrg}
      />

      <Modal
        title="Login"
        isShown={isModalShown}
        hide={hideModal}
        modalContent={<AuthModal returnTo={loginReturnTo} />}
        className={LOGIN_MODAL_WIDTH}
      />
    </>
  )
}

export default TopbarRight

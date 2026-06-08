'use client'

import { usePostHog } from '@/hooks/posthog'
import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { ComponentProps, FormEvent, useCallback } from 'react'
import { twMerge } from 'tailwind-merge'
import { Modal } from '../Modal'
import { useModal } from '../Modal/useModal'
import { AuthModal } from './AuthModal'

interface GetStartedButtonProps extends ComponentProps<typeof Button> {
  text?: string
  orgSlug?: string
}

/**
 * CTA button that opens the signup modal on click.
 *
 * Previously also tracked a ``storefrontOrg`` attribution so signups
 * from a workspace's public storefront were tagged with the source
 * org. That surface was removed in M1.3 (no public workspace
 * profiles in the engineering suite); the attribution path went with
 * it.
 */
const GetStartedButton = ({
  text: _text,
  wrapperClassNames,
  orgSlug: slug,
  size = 'lg',
  ...props
}: GetStartedButtonProps) => {
  const posthog = usePostHog()
  const { isShown: isModalShown, hide: hideModal, show: showModal } = useModal()
  const text = _text || 'Get Started'

  const handleClick = useCallback(() => {
    posthog.capture('global:user:signup:click')
    showModal()
  }, [posthog, showModal])

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault()
      e.stopPropagation()
      handleClick()
    },
    [handleClick],
  )

  return (
    <>
      <Button
        wrapperClassNames={twMerge(
          'flex flex-row items-center gap-x-2',
          wrapperClassNames,
        )}
        size={size}
        onClick={handleClick}
        onSubmit={handleSubmit}
        className="rounded-full bg-(--surface-bold) font-medium text-(--text-inverted) hover:bg-(--surface-bold-hover)"
        {...props}
      >
        <div>{text}</div>
        <Icon
          icon="solar:alt-arrow-right-linear"
          className={`text-[1em] ${size === 'lg' ? 'text-lg' : 'text-md'}`}
        />
      </Button>

      <Modal
        title="Login"
        isShown={isModalShown}
        hide={hideModal}
        modalContent={
          <AuthModal
            returnParams={slug ? { slug, auto: 'true' } : {}}
            signup={{
              intent: 'creator',
            }}
          />
        }
        className="lg:w-full lg:max-w-[480px]"
      />
    </>
  )
}

export default GetStartedButton

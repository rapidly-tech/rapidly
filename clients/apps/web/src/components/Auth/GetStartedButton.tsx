'use client'

import { usePostHog } from '@/hooks/posthog'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { ComponentProps, FormEvent, useCallback, useMemo } from 'react'
import { twMerge } from 'tailwind-merge'
import { Modal } from '../Modal'
import { useModal } from '../Modal/useModal'
import { AuthModal } from './AuthModal'

interface GetStartedButtonProps extends ComponentProps<typeof Button> {
  text?: string
  orgSlug?: string
  storefrontOrg?: schemas['CustomerWorkspace']
}

/**
 * CTA button that opens the signup modal on click.
 * Optionally tracks a storefront attribution if provided.
 */
const GetStartedButton = ({
  text: _text,
  wrapperClassNames,
  orgSlug: slug,
  storefrontOrg,
  size = 'lg',
  ...props
}: GetStartedButtonProps) => {
  const posthog = usePostHog()
  const { isShown: isModalShown, hide: hideModal, show: showModal } = useModal()
  const text = _text || 'Get Started'

  const attribution = useMemo(() => {
    if (!storefrontOrg?.id) return undefined
    return { from_storefront: storefrontOrg.id as string }
  }, [storefrontOrg])

  const handleClick = useCallback(() => {
    posthog.capture('global:user:signup:click', attribution)
    showModal()
  }, [attribution, posthog, showModal])

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
              ...attribution,
            }}
          />
        }
        className="lg:w-full lg:max-w-[480px]"
      />
    </>
  )
}

export default GetStartedButton

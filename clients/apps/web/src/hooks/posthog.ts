'use client'

import type { JsonType } from '@posthog/core'
import type { schemas } from '@rapidly-tech/client'
import { usePostHog as useOuterPostHog } from 'posthog-js/react'
import { useCallback, useMemo } from 'react'

type Surface = 'website' | 'docs' | 'dashboard' | 'storefront' | 'global'

type Category = 'user' | 'workspaces' | 'file_sharing'

type Noun = string

type Verb =
  | 'click'
  | 'submit'
  | 'create'
  | 'view'
  | 'add'
  | 'invite'
  | 'update'
  | 'delete'
  | 'remove'
  | 'start'
  | 'end'
  | 'cancel'
  | 'fail'
  | 'generate'
  | 'send'
  | 'archive'
  | 'done'
  | 'open'
  | 'close'
  | 'complete'

export type EventName = `${Surface}:${Category}:${Noun}:${Verb}`

type PersistenceMode = 'localStorage' | 'sessionStorage' | 'cookie' | 'memory'

export interface RapidlyHog {
  setPersistence: (persistence: PersistenceMode) => void
  capture: (event: EventName, properties?: Record<string, JsonType>) => void
  identify: (user: schemas['UserRead']) => void
  logout: () => void
}

const buildPosthogId = (userId: string): string => `user:${userId}`

export const usePostHog = (): RapidlyHog => {
  const posthog = useOuterPostHog()

  const setPersistence = useCallback(
    (persistence: PersistenceMode) => {
      posthog.set_config({ persistence })
    },
    [posthog],
  )

  const capture = useCallback(
    (event: EventName, properties?: Record<string, JsonType>) => {
      posthog.capture(event, properties)
    },
    [posthog],
  )

  const identify = useCallback(
    (user: schemas['UserRead']) => {
      const desiredId = buildPosthogId(user.id)
      const currentId = posthog.get_distinct_id()

      if (currentId !== desiredId) {
        posthog.identify(desiredId, { email: user.email })
      }
    },
    [posthog],
  )

  const logout = useCallback(() => {
    capture('global:user:logout:done')
    posthog?.reset()
  }, [capture, posthog])

  return useMemo(
    () => ({ setPersistence, capture, identify, logout }),
    [setPersistence, capture, identify, logout],
  )
}

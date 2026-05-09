import { resolvePublicApiUrl } from '@/utils/api'
import { operations } from '@rapidly-tech/client'

type MicrosoftLoginParams = {
  return_to?: string | null
  attribution?: string | null
}

type MicrosoftLinkParams = {
  return_to?: string | null
}

type GoogleLoginParams = NonNullable<
  operations['integrations_google:integrations.google.login.authorize']['parameters']['query']
>

type GoogleLinkParams = NonNullable<
  operations['integrations_google:integrations.google.link.authorize']['parameters']['query']
>

type AppleParams = NonNullable<
  operations['integrations_apple:integrations.apple.authorize']['parameters']['query']
>

const buildAuthUrl = (
  path: string,
  params: Record<string, string | null | undefined>,
): string => {
  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value) searchParams.set(key, value)
  }
  return `${resolvePublicApiUrl()}${path}?${searchParams}`
}

export const getMicrosoftAuthorizeLoginURL = (
  params: MicrosoftLoginParams,
): string =>
  buildAuthUrl('/api/integrations/microsoft/login/authorize', {
    return_to: params.return_to,
    attribution: params.attribution,
  })

export const getMicrosoftAuthorizeLinkURL = (
  params: MicrosoftLinkParams,
): string =>
  buildAuthUrl('/api/integrations/microsoft/link/authorize', {
    return_to: params.return_to,
  })

export const getGoogleAuthorizeLoginURL = (params: GoogleLoginParams): string =>
  buildAuthUrl('/api/integrations/google/login/authorize', {
    return_to: params.return_to,
    attribution: params.attribution,
  })

export const getGoogleAuthorizeLinkURL = (params: GoogleLinkParams): string =>
  buildAuthUrl('/api/integrations/google/link/authorize', {
    return_to: params.return_to,
  })

export const getAppleAuthorizeURL = (params: AppleParams): string =>
  buildAuthUrl('/api/integrations/apple/authorize', {
    return_to: params.return_to,
    attribution: params.attribution,
  })

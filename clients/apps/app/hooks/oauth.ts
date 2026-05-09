/**
 * OAuth2 configuration and authentication flow for the Rapidly mobile app.
 *
 * useOAuthConfig provides endpoint URLs and the client ID for both
 * production and development environments.
 *
 * useOAuth orchestrates the PKCE authorization code flow using the
 * Expo AuthSession library, exchanging the auth code for an access token
 * and persisting it via the SessionProvider.
 */
import { useSession } from '@/providers/SessionProvider'
import {
  exchangeCodeAsync,
  makeRedirectUri,
  useAuthRequest,
} from 'expo-auth-session'
import * as WebBrowser from 'expo-web-browser'
import { useEffect } from 'react'

WebBrowser.maybeCompleteAuthSession()

const OAUTH_SCOPES = [
  'openid',
  'profile',
  'email',
  'web:read',
  'web:write',
  'notifications:read',
  'notifications:write',
  'notification_recipients:read',
  'notification_recipients:write',
]

const PRODUCTION_CONFIG = {
  CLIENT_ID: 'rapidly_ci_yZLBGwoWZVsOdfN5CODRwVSTlJfwJhXqwg65e2CuNMZ',
  discovery: {
    authorizationEndpoint: 'https://rapidly.tech/oauth2/authorize',
    tokenEndpoint: 'https://api.rapidly.tech/api/oauth2/token',
    registrationEndpoint: 'https://api.rapidly.tech/api/oauth2/register',
    revocationEndpoint: 'https://api.rapidly.tech/api/oauth2/revoke',
  },
}

const DEVELOPMENT_CONFIG = {
  CLIENT_ID: 'rapidly_ci_hbFdMZZRghgdm2F4LMceQSrcQNunmjlh6ukGJ1dG0Vg',
  discovery: {
    authorizationEndpoint: `http://127.0.0.1:3000/oauth2/authorize`,
    tokenEndpoint: `${process.env.EXPO_PUBLIC_RAPIDLY_SERVER_URL}/api/oauth2/token`,
    registrationEndpoint: `${process.env.EXPO_PUBLIC_RAPIDLY_SERVER_URL}/api/oauth2/register`,
    revocationEndpoint: `${process.env.EXPO_PUBLIC_RAPIDLY_SERVER_URL}/api/oauth2/revoke`,
  },
}

export const useOAuthConfig = () => ({
  scopes: OAUTH_SCOPES,
  ...PRODUCTION_CONFIG,
})

export const useOAuth = () => {
  const { setSession } = useSession()

  // Warm up the browser for faster auth redirects
  useEffect(() => {
    WebBrowser.warmUpAsync()
    return () => {
      WebBrowser.coolDownAsync()
    }
  }, [])

  const { CLIENT_ID, scopes, discovery } = useOAuthConfig()

  const redirectUri = makeRedirectUri({
    scheme: 'rapidly',
    path: 'oauth/callback',
  })

  const [authRequest, , promptAsync] = useAuthRequest(
    {
      clientId: CLIENT_ID,
      scopes,
      redirectUri,
      usePKCE: true,
      extraParams: { do_not_track: 'true', sub_type: 'user' },
    },
    discovery,
  )

  const authenticate = async () => {
    try {
      const response = await promptAsync({ preferEphemeralSession: true })
      if (response?.type !== 'success') return

      const tokenResult = await exchangeCodeAsync(
        {
          clientId: CLIENT_ID,
          code: response.params.code,
          redirectUri,
          extraParams: { code_verifier: authRequest?.codeVerifier ?? '' },
        },
        discovery,
      )

      setSession(tokenResult.accessToken)
    } catch (err) {
      console.error('[OAuth] Error:', err)
    }
  }

  return { authRequest, authenticate }
}

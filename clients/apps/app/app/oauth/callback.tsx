/**
 * Rapidly OAuth callback route.
 *
 * Handles the OAuth redirect in the Rapidly mobile app by immediately
 * redirecting the user back to the home screen after authentication completes.
 *
 * @module rapidly/app/oauth/callback
 */
import { Redirect } from 'expo-router'

export default function Callback() {
  return <Redirect href="/" />
}

/**
 * Full-screen error fallback for React error boundaries.
 *
 * Detects whether the error is a permissions/auth issue and tailors the
 * recovery action accordingly -- either re-authenticating or logging out.
 */
import React, { useMemo } from 'react'

import { Box } from '@/components/Shared/Box'
import RapidlyLogo from '@/components/Shared/RapidlyLogo'
import { useTheme } from '@/design-system/useTheme'
import { useLogout } from '@/hooks/auth'
import { useOAuth } from '@/hooks/oauth'
import { AuthenticationError } from '@rapidly-tech/client'
import { Text } from '../Shared/Text'
import { Touchable } from '../Shared/Touchable'

export interface ErrorFallbackProps {
  error: unknown
  resetErrorBoundary: () => void
}

/** Returns true when the error indicates an auth or scope problem. */
function isPermissionError(err: unknown): boolean {
  if (err instanceof AuthenticationError) return true
  if (err instanceof Error) {
    const msg = err.message
    return msg.includes('insufficient_scope') || msg.includes('privileges')
  }
  return false
}

export const ErrorFallback = ({
  error,
  resetErrorBoundary,
}: ErrorFallbackProps) => {
  const theme = useTheme()
  const logout = useLogout()
  const { authenticate } = useOAuth()

  const isAuthIssue = isPermissionError(error)

  const heading = useMemo(
    () => (isAuthIssue ? 'Insufficient Permissions' : 'Something Went Wrong'),
    [isAuthIssue],
  )

  const explanation = useMemo(
    () =>
      isAuthIssue
        ? 'You have insufficient permissions to access the resource. Authenticate to gain the necessary permissions.'
        : 'Logout & re-authenticate to try again',
    [isAuthIssue],
  )

  const [buttonLabel, buttonAction] = useMemo(
    () =>
      isAuthIssue
        ? (['Authenticate', authenticate] as const)
        : (['Logout', logout] as const),
    [isAuthIssue, logout, authenticate],
  )

  const handlePress = async () => {
    await buttonAction()
    resetErrorBoundary()
  }

  return (
    <Box
      flex={1}
      justifyContent="center"
      alignItems="center"
      backgroundColor="background"
      gap="spacing-32"
      paddingHorizontal="spacing-24"
    >
      <RapidlyLogo size={80} />

      <Box gap="spacing-12">
        <Text variant="titleLarge" textAlign="center">
          {heading}
        </Text>
        <Text color="subtext" textAlign="center">
          {explanation}
        </Text>
      </Box>

      <Touchable
        activeOpacity={0.6}
        style={{
          backgroundColor: theme.colors.monochromeInverted,
          borderRadius: 100,
          width: 'auto',
          paddingVertical: theme.spacing['spacing-12'],
          paddingHorizontal: theme.spacing['spacing-24'],
        }}
        onPress={handlePress}
      >
        <Text variant="bodyMedium" style={{ color: theme.colors.monochrome }}>
          {buttonLabel}
        </Text>
      </Touchable>
    </Box>
  )
}

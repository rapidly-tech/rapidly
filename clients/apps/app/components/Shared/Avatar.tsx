/**
 * User / workspace avatar with initials fallback.
 *
 * Displays a circular avatar image when available. For Gravatar URLs or
 * missing images the component falls back to the user's initials rendered
 * over a solid-color background. A shimmer placeholder is shown while
 * loading.
 */
import { Box } from '@/components/Shared/Box'
import { Image } from '@/components/Shared/Image/Image'
import { useTheme } from '@/design-system/useTheme'
import { PlaceholderBox } from './PlaceholderBox'
import { Text } from './Text'

/** Extracts up to two initials from a full name. */
function extractInitials(fullName: string): string {
  const parts = fullName.trim().split(' ')
  return parts
    .filter((_, idx) => idx === 0 || idx === parts.length - 1)
    .map((part) => part.charAt(0).toUpperCase())
    .join('')
}

/** Returns true when the avatar URL points at Gravatar (generic placeholder). */
function isGravatarUrl(url: string): boolean {
  if (!url.startsWith('http')) return false
  return new URL(url).host === 'www.gravatar.com'
}

interface AvatarProps {
  name: string
  size?: number
  image?: string | null
  backgroundColor?: string
  loading?: boolean
}

export const Avatar = ({
  name,
  size = 32,
  image,
  backgroundColor,
  loading,
}: AvatarProps) => {
  const theme = useTheme()

  const initials = extractInitials(name ?? '')
  const radius = size / 2
  const shouldShowInitials = !image || isGravatarUrl(image)

  if (loading) {
    return (
      <Box
        alignItems="center"
        justifyContent="center"
        position="relative"
        overflow="hidden"
        style={{ width: size, height: size, borderRadius: radius }}
      >
        <PlaceholderBox
          width={size}
          height={size}
          borderRadius="border-radius-4"
        />
      </Box>
    )
  }

  const bgColor = backgroundColor ?? theme.colors.monochrome

  return (
    <Box
      style={{
        width: size,
        height: size,
        borderRadius: radius,
        backgroundColor: bgColor,
      }}
      alignItems="center"
      justifyContent="center"
      position="relative"
      overflow="hidden"
    >
      {shouldShowInitials ? (
        <Box
          style={{
            width: size,
            height: size,
            borderRadius: radius,
            position: 'absolute',
            inset: 0,
          }}
          alignItems="center"
          justifyContent="center"
        >
          <Text style={{ fontSize: size / 3 }}>{initials}</Text>
        </Box>
      ) : null}

      {image ? (
        <Box position="absolute" style={{ inset: 0 }}>
          <Image
            style={{
              width: size,
              height: size,
              borderRadius: radius,
              position: 'absolute',
              inset: 0,
              zIndex: 1,
              alignItems: 'center',
              justifyContent: 'center',
            }}
            source={{ uri: image }}
          />
        </Box>
      ) : null}
    </Box>
  )
}

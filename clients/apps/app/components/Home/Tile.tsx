/**
 * Square dashboard tile that can navigate via link or fire an onPress callback.
 *
 * Renders children inside a card-styled touchable container with a fixed
 * 1:1 aspect ratio. Supports both Expo Router Link navigation and plain
 * press handlers through a discriminated union prop type.
 */
import { Box } from '@/components/Shared/Box'
import { Href, Link } from 'expo-router'
import { PropsWithChildren } from 'react'
import { Touchable } from '../Shared/Touchable'

export type TileWithLinkProps = PropsWithChildren & { href: Href }
export type TileWithOnPressProps = PropsWithChildren & { onPress: () => void }
export type TileProps = TileWithLinkProps | TileWithOnPressProps

const TILE_STYLE = { aspectRatio: 1 }

function TileContainer({ children }: PropsWithChildren) {
  return (
    <Box
      backgroundColor="card"
      padding="spacing-20"
      borderRadius="border-radius-24"
      flex={1}
      style={TILE_STYLE}
    >
      {children}
    </Box>
  )
}

export const Tile = ({ children, ...props }: TileProps) => {
  if ('href' in props) {
    return (
      <Link href={props.href} asChild>
        <Touchable>
          <TileContainer>{children}</TileContainer>
        </Touchable>
      </Link>
    )
  }

  return (
    <Touchable onPress={props.onPress}>
      <TileContainer>{children}</TileContainer>
    </Touchable>
  )
}

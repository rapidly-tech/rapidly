/**
 * Re-export Restyle's useTheme narrowed to the Rapidly theme type.
 */
// eslint-disable-next-line @rapidly/no-restyle-use-theme
import { useTheme as useRestyleTheme } from '@shopify/restyle'
import type { Theme } from './theme'

export const useTheme = () => useRestyleTheme<Theme>()

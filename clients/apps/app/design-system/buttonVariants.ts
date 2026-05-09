/**
 * Button visual variants for the Rapidly mobile design system.
 *
 * Each variant maps to a set of color tokens that the Button component
 * applies depending on its current state (enabled / disabled).
 */
import { ColorToken } from '@/design-system/theme'

interface ButtonVariantStyle {
  backgroundColor: ColorToken
  textColor: ColorToken
  disabledBackgroundColor: ColorToken
  disabledTextColor: ColorToken
}

export const buttonVariants = {
  primary: {
    backgroundColor: 'monochromeInverted',
    textColor: 'monochrome',
    disabledBackgroundColor: 'disabled',
    disabledTextColor: 'subtext',
  },
  secondary: {
    backgroundColor: 'card',
    textColor: 'monochromeInverted',
    disabledBackgroundColor: 'disabled',
    disabledTextColor: 'subtext',
  },
  destructive: {
    backgroundColor: 'errorSubtle',
    textColor: 'error',
    disabledBackgroundColor: 'disabled',
    disabledTextColor: 'subtext',
  },
} as const satisfies Record<string, ButtonVariantStyle>

export type ButtonVariantKey = keyof typeof buttonVariants

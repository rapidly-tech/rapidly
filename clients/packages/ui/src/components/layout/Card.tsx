import type { ComponentProps } from 'react'

import {
  CardContent as CardContentPrimitive,
  CardDescription as CardDescriptionPrimitive,
  CardFooter as CardFooterPrimitive,
  CardHeader as CardHeaderPrimitive,
  Card as CardPrimitive,
  CardTitle as CardTitlePrimitive,
} from '@/components/primitives/card'
import { twMerge } from 'tailwind-merge'

type PrimitiveProps<T extends React.ElementType> = ComponentProps<T>

// Shared theme tokens
const CARD_SURFACE = 'rounded-2xl glass-card text-foreground'

const DESCRIPTION_TEXT = 'text-sm text-slate-400'

/** Themed card surface with border and background. */
const Card = ({
  ref,
  className,
  ...rest
}: PrimitiveProps<typeof CardPrimitive>) => (
  <CardPrimitive
    ref={ref}
    className={twMerge(CARD_SURFACE, className)}
    {...rest}
  />
)
Card.displayName = CardPrimitive.displayName

/** Top section of a card, typically holding a title and optional actions. */
const CardHeader = ({
  ref,
  className,
  ...rest
}: PrimitiveProps<typeof CardHeaderPrimitive>) => (
  <CardHeaderPrimitive ref={ref} className={twMerge(className)} {...rest} />
)
CardHeader.displayName = CardHeaderPrimitive.displayName

/** Bold heading within a CardHeader. */
const CardTitle = ({
  ref,
  className,
  ...rest
}: PrimitiveProps<typeof CardTitlePrimitive>) => (
  <CardTitlePrimitive ref={ref} className={twMerge(className)} {...rest} />
)
CardTitle.displayName = 'CardTitle'

/** Subdued description beneath a card title. */
const CardDescription = ({
  ref,
  className,
  ...rest
}: PrimitiveProps<typeof CardDescriptionPrimitive>) => (
  <CardDescriptionPrimitive
    ref={ref}
    className={twMerge(DESCRIPTION_TEXT, className)}
    {...rest}
  />
)
CardDescription.displayName = CardDescriptionPrimitive.displayName

/** Primary content region of a card. */
const CardContent = ({
  ref,
  className,
  ...rest
}: PrimitiveProps<typeof CardContentPrimitive>) => (
  <CardContentPrimitive ref={ref} className={twMerge(className)} {...rest} />
)
CardContent.displayName = CardContentPrimitive.displayName

/** Bottom section of a card, usually for action buttons. */
const CardFooter = ({
  ref,
  className,
  ...rest
}: PrimitiveProps<typeof CardFooterPrimitive>) => (
  <CardFooterPrimitive ref={ref} className={twMerge(className)} {...rest} />
)
CardFooter.displayName = CardFooterPrimitive.displayName

export { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle }

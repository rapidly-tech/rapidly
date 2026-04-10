import { Heading, Text } from '@react-email/components'
import { PropsWithChildren } from 'react'

interface IntroProps {
  headline?: string
}

/** Email opening section with an optional headline and body text. */
export function Intro({ headline, children }: PropsWithChildren<IntroProps>) {
  return (
    <>
      {headline && <Heading className="text-lg font-bold">{headline}</Heading>}
      {children && <Text className="text-base">{children}</Text>}
    </>
  )
}

export default Intro

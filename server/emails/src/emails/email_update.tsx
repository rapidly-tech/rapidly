import { Preview, Section } from '@react-email/components'
import Button from '../components/Button'
import Footer from '../components/Footer'
import Intro from '../components/Intro'
import WrapperRapidly from '../components/WrapperRapidly'
import type { schemas } from '../types'

/** Confirmation email sent when a user changes their email address. */
export function EmailUpdate({
  email,
  token_lifetime_minutes,
  url,
}: schemas['EmailUpdateProps']) {
  return (
    <WrapperRapidly>
      <Preview>Here is the verification link to update your email</Preview>
      <Intro>
        Here is the verification link to update your email. Click the button
        below to complete the update process.{' '}
        <span className="font-bold">
          This link is only valid for the next {token_lifetime_minutes} minutes.
        </span>
      </Intro>

      <Section className="my-8 text-center">
        <Button href={url}>Update email</Button>
      </Section>

      <Footer email={email} />
    </WrapperRapidly>
  )
}

EmailUpdate.PreviewProps = {
  email: 'john@example.com',
  token_lifetime_minutes: 30,
  url: 'https://rapidly.tech/settings/account/email/update?token=abc123',
}

export default EmailUpdate

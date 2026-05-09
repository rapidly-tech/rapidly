import { Preview, Section } from '@react-email/components'
import BodyText from '../components/BodyText'
import Footer from '../components/Footer'
import Intro from '../components/Intro'
import WrapperRapidly from '../components/WrapperRapidly'
import type { schemas } from '../types'

/** Notification email when an organisation's verification review is complete. */
export function OrganizationReviewed({
  email,
  organization,
}: schemas['OrganizationReviewedProps']) {
  return (
    <WrapperRapidly>
      <Preview>
        Great news! Your organization has been approved and you&apos;re ready to
        start selling
      </Preview>
      <Intro>
        Great news! Your organization <strong>{organization.name}</strong> has
        been approved.
      </Intro>
      <Section>
        <BodyText>
          You&apos;re now all set to start sharing files on Rapidly. You can create
          file shares and start accepting payments from
          customers around the world.
        </BodyText>
        <BodyText>
          <strong>What&apos;s next?</strong>
        </BodyText>
        <BodyText>
          Head to your dashboard to start sharing files and
          integrate Rapidly into your workflow.
        </BodyText>
        <BodyText>
          If you have any questions as you get started, our support team is here
          to help.
        </BodyText>
      </Section>
      <Footer email={email} />
    </WrapperRapidly>
  )
}

OrganizationReviewed.PreviewProps = {
  email: 'admin@example.com',
  organization: {
    id: '123e4567-e89b-12d3-a456-426614174000',
    name: 'Acme Inc.',
    slug: 'acme-inc',
    avatar_url: 'https://avatars.githubusercontent.com/u/105373340?s=200&v=4',
  },
}

export default OrganizationReviewed

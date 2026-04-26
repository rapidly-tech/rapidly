import { Preview, Section, Text } from '@react-email/components'
import Button from '../components/Button'
import Footer from '../components/Footer'
import Intro from '../components/Intro'
import WrapperRapidly from '../components/WrapperRapidly'
import type { schemas } from '../types'

/** Invitation email to join an organisation as a team member. */
export function OrganizationInvite({
  email,
  organization_name,
  inviter_email,
  invite_url,
}: schemas['OrganizationInviteProps']) {
  return (
    <WrapperRapidly>
      <Preview>You've been added to {organization_name} on Rapidly</Preview>
      <Intro>
        {inviter_email} has added you to{' '}
        <span className="font-bold">{organization_name}</span> on Rapidly.
      </Intro>
      <Section>
        <Text>
          As a member of {organization_name} you're now able to manage{' '}
          {organization_name}'s file shares, customers, and payments on Rapidly.
        </Text>
      </Section>
      <Section className="text-center">
        <Button href={invite_url}>Go to the Rapidly dashboard</Button>
      </Section>
      <Footer email={email} />
    </WrapperRapidly>
  )
}

OrganizationInvite.PreviewProps = {
  email: 'john@example.com',
  organization_name: 'Acme Inc.',
  inviter_email: 'admin@acme.com',
  invite_url: 'https://rapidly.tech/dashboard/acme-inc',
}

export default OrganizationInvite

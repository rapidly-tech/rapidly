import { Preview, Section, Text } from '@react-email/components'
import Button from '../components/Button'
import Footer from '../components/Footer'
import Intro from '../components/Intro'
import WrapperRapidly from '../components/WrapperRapidly'
import type { schemas } from '../types'

/** Invitation email to join an organisation as a team member. */
export function OrganizationInvite({
  email,
  workspace_name,
  inviter_email,
  invite_url,
}: schemas['WorkspaceInviteProps']) {
  return (
    <WrapperRapidly>
      <Preview>You've been added to {workspace_name} on Rapidly</Preview>
      <Intro>
        {inviter_email} has added you to{' '}
        <span className="font-bold">{workspace_name}</span> on Rapidly.
      </Intro>
      <Section>
        <Text>
          As a member of {workspace_name} you're now able to manage{' '}
          {workspace_name}'s file shares, customers, and payments on Rapidly.
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
  workspace_name: 'Acme Inc.',
  inviter_email: 'admin@acme.com',
  invite_url: 'https://rapidly.tech/dashboard/acme-inc',
}

export default OrganizationInvite

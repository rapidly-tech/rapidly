import { Preview } from '@react-email/components'
import BodyText from '../components/BodyText'
import Button from '../components/Button'
import Footer from '../components/Footer'
import Intro from '../components/Intro'
import WrapperRapidly from '../components/WrapperRapidly'
import type { schemas } from '../types'

/** Notification email prompting a user to create their account. */
export function NotificationCreateAccount({
  workspace_name,
  url,
}: schemas['MaintainerCreateAccountNotificationPayload']) {
  return (
    <WrapperRapidly>
      <Preview>Your Rapidly account is being reviewed</Preview>
      <Intro>
        Now that you got your first payment to {workspace_name}, you should
        create a payout account in order to receive your funds.
      </Intro>
      <BodyText>
        This operation only takes a few minutes and allows you to receive your
        money immediately.
      </BodyText>
      <Button href={url}>Create payout account</Button>

      <Footer email={null} />
    </WrapperRapidly>
  )
}

NotificationCreateAccount.PreviewProps = {
  workspace_name: 'Acme Inc.',
  url: 'https://rapidly.tech',
}

export default NotificationCreateAccount

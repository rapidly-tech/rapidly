import { Preview } from '@react-email/components'
import BodyText from '../components/BodyText'
import Footer from '../components/Footer'
import Intro from '../components/Intro'
import WrapperRapidly from '../components/WrapperRapidly'
import type { schemas } from '../types'

/** Notification email when a payment is received for a shared file. */
export function NotificationFileSharePaymentReceived({
  file_name,
  formatted_amount,
}: schemas['FileSharePaymentReceivedNotificationPayload']) {
  return (
    <WrapperRapidly>
      <Preview>
        Payment received for {file_name}: {formatted_amount}
      </Preview>
      <Intro>
        Payment received for {file_name}: {formatted_amount}
      </Intro>
      <BodyText>
        Someone has paid to access your shared file. You can view your earnings
        and sharing activity in the Rapidly dashboard.
      </BodyText>

      <Footer email={null} />
    </WrapperRapidly>
  )
}

NotificationFileSharePaymentReceived.PreviewProps = {
  file_name: 'report.pdf',
  formatted_amount: '$5.00 USD',
}

export default NotificationFileSharePaymentReceived

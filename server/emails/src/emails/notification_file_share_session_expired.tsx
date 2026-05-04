import { Preview } from '@react-email/components'
import BodyText from '../components/BodyText'
import Footer from '../components/Footer'
import Intro from '../components/Intro'
import WrapperRapidly from '../components/WrapperRapidly'
import type { schemas } from '../types'

/** Notification email when a share link expires. */
export function NotificationFileShareSessionExpired({
  file_name,
}: schemas['FileShareSessionExpiredNotificationPayload']) {
  return (
    <WrapperRapidly>
      <Preview>Your share link has expired: {file_name}</Preview>
      <Intro>Your share link has expired: {file_name}</Intro>
      <BodyText>
        The share link for your file is no longer active. Recipients will no
        longer be able to download this file. You can create a new share link
        from the Rapidly dashboard.
      </BodyText>

      <Footer email={null} />
    </WrapperRapidly>
  )
}

NotificationFileShareSessionExpired.PreviewProps = {
  file_name: 'report.pdf',
}

export default NotificationFileShareSessionExpired

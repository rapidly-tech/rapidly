import { Preview } from '@react-email/components'
import BodyText from '../components/BodyText'
import Footer from '../components/Footer'
import Intro from '../components/Intro'
import WrapperRapidly from '../components/WrapperRapidly'
import type { schemas } from '../types'

/** Notification email when someone downloads a shared file. */
export function NotificationFileShareDownloadCompleted({
  file_name,
}: schemas['FileShareDownloadCompletedNotificationPayload']) {
  return (
    <WrapperRapidly>
      <Preview>Someone downloaded your file: {file_name}</Preview>
      <Intro>Someone downloaded your file: {file_name}</Intro>
      <BodyText>
        A recipient has successfully downloaded your shared file. You can view
        your sharing activity in the Rapidly dashboard.
      </BodyText>

      <Footer email={null} />
    </WrapperRapidly>
  )
}

NotificationFileShareDownloadCompleted.PreviewProps = {
  file_name: 'report.pdf',
}

export default NotificationFileShareDownloadCompleted

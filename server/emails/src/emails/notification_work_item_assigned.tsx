import { Button, Preview } from '@react-email/components'
import BodyText from '../components/BodyText'
import Footer from '../components/Footer'
import Intro from '../components/Intro'
import WrapperRapidly from '../components/WrapperRapidly'
import type { schemas } from '../types'

/** Notification email when a user is assigned to a work item. */
export function NotificationWorkItemAssigned({
  project_name,
  work_item_name,
  work_item_url,
}: schemas['WorkItemAssignedNotificationPayload']) {
  return (
    <WrapperRapidly>
      <Preview>
        You were assigned to {work_item_name} in {project_name}
      </Preview>
      <Intro>You were assigned: {work_item_name}</Intro>
      <BodyText>
        You have been assigned to a work item in <strong>{project_name}</strong>.
        Open it to see the details.
      </BodyText>
      <Button
        href={work_item_url}
        style={{
          background: '#10b981',
          color: '#ffffff',
          padding: '10px 18px',
          borderRadius: '6px',
          fontWeight: 600,
        }}
      >
        Open work item
      </Button>

      <Footer email={null} />
    </WrapperRapidly>
  )
}

NotificationWorkItemAssigned.PreviewProps = {
  project_name: 'Launch Plan',
  work_item_name: 'Wire payments to landing CTA',
  work_item_url: 'https://app.rapidly.tech/preview/projects/x',
}

export default NotificationWorkItemAssigned

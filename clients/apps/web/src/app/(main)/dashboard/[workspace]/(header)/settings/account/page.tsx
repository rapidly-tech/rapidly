import { DashboardBody } from '@/components/Layout/DashboardLayout'
import AuthenticationSettings from '@/components/Settings/AuthenticationSettings'
import { NotificationRecipientsSettings } from '@/components/Settings/NotificationRecipientsSettings'
import { Section, SectionDescription } from '@/components/Settings/Section'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Account Settings',
}

export default function Page() {
  return (
    <DashboardBody
      title="Settings"
      wrapperClassName="max-w-(--breakpoint-sm)!"
      className="gap-y-8 pb-16 md:gap-y-12"
    >
      <div className="flex flex-col gap-y-12">
        <Section id="connections">
          <SectionDescription
            title="Account Connections"
            description="Manage third-party connections to your account"
          />
          <AuthenticationSettings />
        </Section>

        <Section id="notifications">
          <SectionDescription
            title="Notification Recipients"
            description="Manage the devices which receive notifications"
          />
          <NotificationRecipientsSettings />
        </Section>
      </div>
    </DashboardBody>
  )
}

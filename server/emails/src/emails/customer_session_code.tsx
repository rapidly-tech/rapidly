import { Link, Preview, Text } from '@react-email/components'
import FooterCustomer from '../components/FooterCustomer'
import Intro from '../components/Intro'
import OTPCode from '../components/OTPCode'
import WrapperOrganization from '../components/WrapperOrganization'
import { workspace } from '../preview'
import type { schemas } from '../types'

/** Customer portal login email with a one-time verification code. */
export function CustomerSessionCode({
  email,
  workspace,
  code,
  code_lifetime_minutes,
  url,
}: schemas['CustomerSessionCodeProps']) {
  return (
    <WrapperOrganization workspace={workspace}>
      <Preview>Your verification code for {workspace.name}</Preview>
      <Intro>
        You can use the following code to access your purchases on the{' '}
        <Link href={url} className="text-blue-500 underline">
          {workspace.name} Customer Portal
        </Link>
        .
      </Intro>

      <OTPCode code={code} domain="rapidly.tech" />

      <Text className="mt-2 text-center text-sm text-gray-500">
        This&nbsp;code&nbsp;expires&nbsp;in&nbsp;
        {code_lifetime_minutes}
        &nbsp;minutes.
      </Text>

      <FooterCustomer workspace={workspace} email={email} />
    </WrapperOrganization>
  )
}

CustomerSessionCode.PreviewProps = {
  email: 'john@example.com',
  workspace,
  code: 'ABC123',
  code_lifetime_minutes: 30,
  url: 'https://rapidly.tech/acme-inc/portal/authenticate',
}

export default CustomerSessionCode

import { Hr, Section, Text } from '@react-email/components'
import { schemas } from '../types'

/** Organisation-branded email footer with customer support links. */
const FooterCustomer = ({
  organization,
  email,
}: {
  organization: schemas['Organization']
  email: string
}) => (
  <>
    <Hr className="mt-8" />
    <Section className="text-center">
      <Text className="text-xs text-gray-400">
        This email was sent to{' '}
        <span className="text-gray-500">
          <a
            href={`mailto:${email}`}
            className="font-medium text-gray-500"
            style={{
              textDecoration: 'none !important',
              color: 'inherit !important',
            }}
          >
            <span
              style={{
                textDecoration: 'none !important',
                color: 'inherit !important',
              }}
            >
              {email}
            </span>
          </a>
        </span>
        .
      </Text>
      <Text className="text-xs text-gray-400">
        Payment processing services provided to{' '}
        <span className="font-medium text-gray-500">{organization.name}</span>{' '}
        by{' '}
        <span className="font-medium text-gray-500">Rapidly Software Ltd.</span>
      </Text>
    </Section>
  </>
)

export default FooterCustomer

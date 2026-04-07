import { Hr, Section, Text } from '@react-email/components'

/** Email footer with recipient address and company name. */
const Footer = ({ email }: { email: string | null }) => (
  <>
    <Hr />
    <Section className="text-center text-sm">
      {email && (
        <Text className="mb-2 text-gray-500">
          This email was sent to{' '}
          <a
            href={`mailto:${email}`}
            className="font-semibold"
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
          .
        </Text>
      )}
      <Text className="font-semibold text-gray-900">&copy; 2026 Rapidly</Text>
    </Section>
  </>
)

export default Footer

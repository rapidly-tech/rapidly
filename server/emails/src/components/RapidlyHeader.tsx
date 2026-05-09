import { Img, Link, Section } from '@react-email/components'

/** Rapidly logo badge header for platform-branded transactional emails. */
const Header = () => (
  <Section>
    <Link href="https://rapidly.tech" target="_blank">
      <Img
        alt="Rapidly Logo"
        height="48"
        src="https://uploads.rapidly.tech/emails/rapidly-logo.png"
      />
    </Link>
  </Section>
)

export default Header

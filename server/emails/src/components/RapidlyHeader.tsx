import { Img, Section } from '@react-email/components'

interface HeaderProps {}

/** Rapidly logo badge header for platform-branded transactional emails. */
const Header = () => (
  <Section>
    <div className="relative h-[48px]">
      <Img
        alt="Rapidly Logo"
        height="48"
        src="https://uploads.rapidly.tech/emails/rapidly-logo.png"
      />
    </div>
  </Section>
)

export default Header

import { Container } from '@react-email/components'
import { schemas } from '../types'
import OrganizationHeader from './OrganizationHeader'
import WrapperBase from './WrapperBase'

/** Organisation-branded email layout with the org avatar and name header. */
const WrapperOrganization = ({
  children,
  workspace,
}: {
  children: React.ReactNode
  workspace: schemas['Workspace']
}) => {
  return (
    <WrapperBase>
      <Container className="px-[20px] pt-[20px] pb-[10px]">
        <OrganizationHeader workspace={workspace} />
      </Container>
      <Container className="px-[20px] pt-[10px] pb-[20px]">
        {children}
      </Container>
    </WrapperBase>
  )
}

export default WrapperOrganization

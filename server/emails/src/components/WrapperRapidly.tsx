import { Container } from '@react-email/components'
import RapidlyHeader from './RapidlyHeader'
import WrapperBase from './WrapperBase'

/** Platform-branded email layout with the Rapidly logo header. */
const WrapperRapidly = ({ children }: { children: React.ReactNode }) => {
  return (
    <WrapperBase>
      <Container className="px-[12px] pt-[20px] pb-[10px]">
        <RapidlyHeader />
      </Container>
      <Container className="px-[20px] pt-[10px] pb-[20px]">
        {children}
      </Container>
    </WrapperBase>
  )
}

export default WrapperRapidly

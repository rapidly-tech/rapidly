import { CustomerPortalOverview } from '@/components/CustomerPortal/CustomerPortalOverview'
import { schemas } from '@rapidly-tech/client'

const ClientPage = ({
  workspace,
  customerSessionToken,
}: {
  workspace: schemas['CustomerWorkspace']
  customerSessionToken: string
}) => {
  return (
    <CustomerPortalOverview
      workspace={workspace}
      customerSessionToken={customerSessionToken}
    />
  )
}

export default ClientPage

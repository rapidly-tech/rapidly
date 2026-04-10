import { Storefront } from '@/components/Profile/Storefront'
import { StorefrontFileShare, StorefrontSecret } from '@/utils/storefront'
import { schemas } from '@rapidly-tech/client'

const ClientPage = ({
  workspace,
  fileShares,
  secrets = [],
}: {
  workspace: schemas['CustomerWorkspace']
  fileShares: StorefrontFileShare[]
  secrets?: StorefrontSecret[]
}) => {
  return (
    <Storefront
      workspace={workspace}
      fileShares={fileShares}
      secrets={secrets}
    />
  )
}

export default ClientPage

'use client'

import { InlineModal } from '@/components/Modal/InlineModal'
import { useModal } from '@/components/Modal/useModal'
import { useOAuth2Clients } from '@/hooks/api/oauth'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Avatar from '@rapidly-tech/ui/components/data/Avatar'
import FormattedDateTime from '@rapidly-tech/ui/components/data/FormattedDateTime'
import Button from '@rapidly-tech/ui/components/forms/Button'
import ItemGroup from '@rapidly-tech/ui/components/navigation/ItemGroup'
import { useCallback, useState } from 'react'
import { EditOAuthClientModal } from './EditOAuthClientModal'
import { NewOAuthClientModal } from './NewOAuthClientModal'

// ---------------------------------------------------------------------------
// OAuth Settings — lists registered OAuth2 applications and provides
// create / edit modals for managing them.
// ---------------------------------------------------------------------------

const OAuthSettings = () => {
  const oauthClients = useOAuth2Clients()

  const {
    isShown: isNewModalShown,
    show: showNewModal,
    hide: hideNewModal,
  } = useModal()

  const {
    isShown: isEditModalShown,
    hide: hideEditModal,
    show: showEditModal,
  } = useModal()

  const [activeClient, setActiveClient] = useState<
    schemas['OAuth2Client'] | undefined
  >()

  const handleCreated = useCallback(
    (client: schemas['OAuth2Client']) => {
      hideNewModal()
      setActiveClient(client)
      showEditModal()
    },
    [hideNewModal, showEditModal],
  )

  const handleOpen = useCallback(
    (client: schemas['OAuth2Client']) => {
      setActiveClient(client)
      showEditModal()
    },
    [showEditModal],
  )

  const clients = oauthClients.data?.data

  return (
    <ItemGroup>
      {clients && clients.length > 0 ? (
        clients.map((client) => (
          <ItemGroup.Item key={client.client_id}>
            <OAuthClientRow client={client} onClick={handleOpen} />
          </ItemGroup.Item>
        ))
      ) : (
        <ItemGroup.Item>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No OAuth applications have been registered yet.
          </p>
        </ItemGroup.Item>
      )}
      <ItemGroup.Item>
        <Button asChild onClick={showNewModal}>
          New OAuth App
        </Button>
      </ItemGroup.Item>
      <InlineModal
        isShown={isNewModalShown}
        hide={hideNewModal}
        modalContent={
          <NewOAuthClientModal
            onSuccess={handleCreated}
            onHide={hideNewModal}
          />
        }
      />
      <InlineModal
        isShown={isEditModalShown}
        hide={hideEditModal}
        modalContent={
          activeClient ? (
            <EditOAuthClientModal
              client={activeClient}
              onSuccess={hideEditModal}
              onDelete={hideEditModal}
              onHide={hideEditModal}
            />
          ) : (
            <></>
          )
        }
      />
    </ItemGroup>
  )
}

// ---------------------------------------------------------------------------
// Row component — displays a single OAuth client with avatar and creation date
// ---------------------------------------------------------------------------

interface OAuthClientRowProps {
  client: schemas['OAuth2Client']
  onClick: (client: schemas['OAuth2Client']) => void
}

const OAuthClientRow = ({ client, onClick }: OAuthClientRowProps) => (
  <div
    className="flex w-full cursor-pointer flex-col gap-y-4"
    onClick={() => onClick(client)}
  >
    <div className="flex flex-row items-center justify-between">
      <div className="flex flex-row items-center gap-x-4">
        <Avatar
          className="h-12 w-12"
          avatar_url={client.logo_uri || null}
          name={client.client_name}
        />
        <div className="flex flex-col">
          <h3 className="text-md mr-4 text-ellipsis whitespace-nowrap">
            {client.client_name}
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            <FormattedDateTime datetime={client.created_at} dateStyle="long" />
          </p>
        </div>
      </div>
      <Button variant="secondary">
        <Icon icon="solar:arrow-right-linear" className="text-[1em]" />
      </Button>
    </div>
  </div>
)

export default OAuthSettings

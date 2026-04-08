import { ConfirmModal } from '@/components/Modal/ConfirmModal'
import { InlineModalHeader } from '@/components/Modal/InlineModal'
import { useModal } from '@/components/Modal/useModal'
import { toast } from '@/components/Toast/use-toast'
import { useDeleteOAuthClient, useUpdateOAuth2Client } from '@/hooks/api/oauth'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { ResponsivePanel } from '@rapidly-tech/ui/components/layout/ElevatedCard'
import { Form } from '@rapidly-tech/ui/components/primitives/form'
import { useCallback } from 'react'
import { useForm } from 'react-hook-form'
import {
  FieldClientID,
  FieldClientSecret,
  FieldClientType,
  FieldClientURI,
  FieldLogo,
  FieldName,
  FieldPrivacy,
  FieldRedirectURIs,
  FieldScopes,
  FieldTOS,
} from './OAuthForm'

export interface EnhancedOAuth2ClientConfigurationUpdate extends Omit<
  schemas['OAuth2ClientConfigurationUpdate'],
  'redirect_uris' | 'scope'
> {
  redirect_uris: { uri: string }[]
  scope: string[]
}

interface EditOAuthClientModalProps {
  client: schemas['OAuth2Client']
  onSuccess: (client: schemas['OAuth2Client']) => void
  onDelete: (client: schemas['OAuth2Client']) => void
  onHide: () => void
}

/**
 * Full-screen modal for editing an existing OAuth2 client application.
 * Provides update + delete actions with a confirmation dialog for deletion.
 */
export const EditOAuthClientModal = ({
  client,
  onSuccess,
  onDelete,
  onHide,
}: EditOAuthClientModalProps) => {
  const {
    hide: hideDeleteModal,
    isShown: isDeleteModalShown,
    show: showDeleteModal,
  } = useModal()

  const form = useForm<EnhancedOAuth2ClientConfigurationUpdate>({
    defaultValues: {
      ...client,
      redirect_uris: client.redirect_uris.map((uri) => ({ uri })),
      scope: client.scope?.split(' ') ?? [],
    },
  })

  const { handleSubmit } = form
  const updateOAuth2Client = useUpdateOAuth2Client()

  const onSubmit = useCallback(
    async (values: EnhancedOAuth2ClientConfigurationUpdate) => {
      const { data, error } = await updateOAuth2Client.mutateAsync({
        client_id: client.client_id,
        body: {
          ...values,
          redirect_uris: values.redirect_uris.map(({ uri }) => uri),
          scope: values.scope.join(' '),
        },
      })

      if (error) {
        toast({
          title: 'OAuth App Update Failed',
          description: `Could not update OAuth app: ${error.detail}`,
        })
        return
      }

      const updated = data as schemas['OAuth2Client']
      toast({
        title: 'OAuth App Updated',
        description: `${client.client_name} has been saved`,
      })
      onSuccess(updated)
    },
    [onSuccess, updateOAuth2Client, client],
  )

  const deleteOAuthClient = useDeleteOAuthClient()

  const handleDeleteOAuthClient = useCallback(async () => {
    const { error } = await deleteOAuthClient.mutateAsync(client.client_id)
    if (error) {
      toast({
        title: 'OAuth App Deletion Failed',
        description: `Could not delete OAuth app: ${error.detail}`,
      })
      return
    }
    toast({
      title: 'OAuth App Deleted',
      description: `${client.client_name} has been removed`,
    })
    hideDeleteModal()
    onDelete(client)
  }, [hideDeleteModal, onDelete, client, deleteOAuthClient])

  return (
    <div className="flex flex-col">
      <InlineModalHeader hide={onHide}>
        <h2 className="text-xl">Edit OAuth App</h2>
      </InlineModalHeader>
      <div className="flex flex-col gap-y-8 p-8">
        <Form {...form}>
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="max-w-[700px] space-y-8"
          >
            <FieldName />
            <FieldClientID clientId={client.client_id} />
            <FieldClientSecret clientSecret={client.client_secret} />
            <FieldClientType />
            <FieldLogo />
            <FieldRedirectURIs />
            <FieldScopes />
            <FieldClientURI />
            <FieldTOS />
            <FieldPrivacy />

            <ResponsivePanel className="flex flex-col gap-y-8 md:bg-slate-100 md:dark:bg-slate-800">
              <div className="flex flex-row items-start justify-between">
                <div className="flex flex-col gap-y-1">
                  <h3 className="rp-text-primary font-medium">
                    Delete OAuth Application
                  </h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    This action is permanent and cannot be reversed.
                  </p>
                </div>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={(e: React.MouseEvent) => {
                    e.preventDefault()
                    e.stopPropagation()
                    showDeleteModal()
                  }}
                >
                  Delete
                </Button>
              </div>
              <ConfirmModal
                title="Delete OAuth Application"
                description="All tokens issued by this client will stop working immediately. Continue?"
                destructiveText="Delete"
                onConfirm={handleDeleteOAuthClient}
                isShown={isDeleteModalShown}
                hide={hideDeleteModal}
                destructive
              />
            </ResponsivePanel>

            <Button
              type="submit"
              loading={updateOAuth2Client.isPending}
              disabled={updateOAuth2Client.isPending}
            >
              Update
            </Button>
          </form>
        </Form>
      </div>
    </div>
  )
}

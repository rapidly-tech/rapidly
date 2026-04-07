import { InlineModalHeader } from '@/components/Modal/InlineModal'
import { toast } from '@/components/Toast/use-toast'
import { useCreateOAuth2Client } from '@/hooks/api/oauth'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { Form } from '@rapidly-tech/ui/components/primitives/form'
import { useCallback, useState } from 'react'
import { useForm } from 'react-hook-form'
import {
  FieldClientType,
  FieldClientURI,
  FieldLogo,
  FieldName,
  FieldPrivacy,
  FieldRedirectURIs,
  FieldScopes,
  FieldTOS,
} from './OAuthForm'

export interface EnhancedOAuth2ClientConfiguration extends Omit<
  schemas['OAuth2ClientConfiguration'],
  'redirect_uris' | 'scope'
> {
  redirect_uris: { uri: string }[]
  scope: string[]
}

interface NewOAuthClientModalProps {
  onSuccess: (client: schemas['OAuth2Client']) => void
  onHide: () => void
}

const FORM_DEFAULTS: Partial<EnhancedOAuth2ClientConfiguration> = {
  token_endpoint_auth_method: 'client_secret_post',
  redirect_uris: [{ uri: '' }],
  scope: [],
}

export const NewOAuthClientModal = ({
  onSuccess,
  onHide,
}: NewOAuthClientModalProps) => {
  const form = useForm<EnhancedOAuth2ClientConfiguration>({
    defaultValues: FORM_DEFAULTS,
  })

  const { handleSubmit } = form
  const [hasCreated, setHasCreated] = useState(false)
  const createOAuth2Client = useCreateOAuth2Client()

  const onSubmit = useCallback(
    async (values: EnhancedOAuth2ClientConfiguration) => {
      const payload = {
        ...values,
        redirect_uris: values.redirect_uris.map(({ uri }) => uri),
        scope: values.scope.join(' '),
      }

      const { data, error } = await createOAuth2Client.mutateAsync(payload)

      if (error) {
        toast({
          title: 'OAuth App Creation Failed',
          description: `Could not create OAuth app: ${error.detail}`,
        })
        return
      }

      const created = data as schemas['OAuth2Client']
      toast({
        title: 'OAuth App Created',
        description: `${created.client_name} is ready to use`,
      })
      setHasCreated(true)
      onSuccess(created)
    },
    [createOAuth2Client, onSuccess],
  )

  return (
    <div className="flex flex-col">
      <InlineModalHeader hide={onHide}>
        <h2 className="text-xl">New OAuth App</h2>
      </InlineModalHeader>
      <div className="flex flex-col gap-y-8 p-8">
        <Form {...form}>
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="max-w-[700px] space-y-8"
          >
            <FieldName />
            <FieldLogo />
            <FieldClientType />
            <FieldRedirectURIs />
            <FieldScopes />
            <FieldClientURI />
            <FieldTOS />
            <FieldPrivacy />

            <Button
              type="submit"
              loading={createOAuth2Client.isPending}
              disabled={hasCreated}
            >
              Create
            </Button>
          </form>
        </Form>
      </div>
    </div>
  )
}

'use client'

import { InlineModalHeader } from '@/components/Modal/InlineModal'
import { toast } from '@/components/Toast/use-toast'
import { useCreateWebhookEndpoint } from '@/hooks/api'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { Form } from '@rapidly-tech/ui/components/primitives/form'
import { useRouter } from 'next/navigation'
import { useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { FieldEvents, FieldFormat, FieldUrl } from './WebhookForm'

export default function NewWebhookModal({
  workspace,
  hide,
}: {
  workspace: schemas['Workspace']
  hide: () => void
}) {
  const router = useRouter()
  const form = useForm<schemas['WebhookEndpointCreate']>({
    defaultValues: {
      workspace_id: workspace.id,
    },
  })

  const { handleSubmit } = form

  const createWebhookEndpoint = useCreateWebhookEndpoint()

  const onSubmit = useCallback(
    async (form: schemas['WebhookEndpointCreate']) => {
      const { data, error } = await createWebhookEndpoint.mutateAsync(form)
      if (error) {
        toast({
          title: 'Webhook Endpoint Creation Failed',
          description: `Error creating Webhook Endpoint: ${error.detail}`,
        })
        return
      }
      toast({
        title: 'Webhook Endpoint Created',
        description: `Webhook Endpoint was created successfully`,
      })
      router.push(
        `/dashboard/${workspace.slug}/settings/webhooks/endpoints/${data.id}`,
      )
    },
    [createWebhookEndpoint, router, workspace.slug],
  )

  return (
    <div className="flex flex-col overflow-y-auto">
      <InlineModalHeader hide={hide}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-xl">New webhook</h2>
        </div>
      </InlineModalHeader>
      <div className="flex flex-col gap-y-8 p-8">
        <Form {...form}>
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="max-w-[700px] space-y-8"
          >
            <FieldUrl />
            <FieldFormat />
            <FieldEvents />

            <Button
              type="submit"
              loading={createWebhookEndpoint.isPending}
              disabled={createWebhookEndpoint.isPending}
            >
              Create
            </Button>
          </form>
        </Form>
      </div>
    </div>
  )
}

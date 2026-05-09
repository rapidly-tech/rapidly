'use client'

import { DashboardBody } from '@/components/Layout/DashboardLayout'
import {
  FieldEvents,
  FieldFormat,
  FieldUrl,
} from '@/components/Settings/Webhook/WebhookForm'
import { toast } from '@/components/Toast/use-toast'
import { useEditWebhookEndpoint } from '@/hooks/api'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { Form } from '@rapidly-tech/ui/components/primitives/form'
import { useCallback } from 'react'
import { useForm } from 'react-hook-form'

type EndpointUpdate = schemas['WebhookEndpointUpdate']

export default function WebhookContextView({
  endpoint,
}: {
  endpoint: schemas['WebhookEndpoint']
}) {
  const form = useForm<EndpointUpdate>({
    defaultValues: { ...endpoint },
  })

  const { handleSubmit } = form
  const updateEndpoint = useEditWebhookEndpoint()
  const isPending = updateEndpoint.isPending

  const onSubmit = useCallback(
    async (values: EndpointUpdate) => {
      const { error } = await updateEndpoint.mutateAsync({
        id: endpoint.id,
        body: values,
      })

      if (error) {
        toast({
          title: 'Update Failed',
          description: `Could not update webhook endpoint: ${error.detail}`,
        })
        return
      }

      toast({
        title: 'Endpoint Updated',
        description: 'Webhook endpoint has been saved',
      })
    },
    [endpoint.id, updateEndpoint],
  )

  return (
    <DashboardBody>
      <div className="flex flex-col gap-8">
        <Form {...form}>
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="flex max-w-[700px] flex-col gap-y-4"
          >
            <FieldUrl />
            <FieldFormat />
            <FieldEvents />

            <Button type="submit" loading={isPending} disabled={isPending}>
              Save
            </Button>
          </form>
        </Form>
      </div>
    </DashboardBody>
  )
}

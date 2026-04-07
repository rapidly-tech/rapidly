'use client'

import { DashboardBody } from '@/components/Layout/DashboardLayout'
import { DateRange } from '@/components/Metrics/DateRangePicker'
import { ConfirmModal } from '@/components/Modal/ConfirmModal'
import { useModal } from '@/components/Modal/useModal'
import WebhookContextView from '@/components/Settings/Webhook/WebhookContextView'
import DeliveriesTable from '@/components/Settings/Webhook/WebhookDeliveriesTable'
import { WebhookFilter } from '@/components/Settings/Webhook/WebhookFilter'
import { toast } from '@/components/Toast/use-toast'
import { getStatusRedirect } from '@/components/Toast/utils'
import {
  useDeleteWebhookEndpoint,
  useEditWebhookEndpoint,
  useResetSecretWebhookEndpoint,
  useWebhookEndpoint,
} from '@/hooks/api'
import {
  DataTablePaginationState,
  DataTableSortingState,
} from '@/utils/datatable'
import { operations, schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import CopyToClipboardInput from '@rapidly-tech/ui/components/forms/CopyToClipboardInput'
import Switch from '@rapidly-tech/ui/components/forms/Switch'
import { useParams, useRouter } from 'next/navigation'
import { parseAsArrayOf, parseAsString, useQueryState } from 'nuqs'
import { useCallback, useState } from 'react'

// ── Main Component ──

export default function ClientPage({
  workspace,
  pagination,
  sorting,
}: {
  workspace: schemas['Workspace']
  pagination: DataTablePaginationState
  sorting: DataTableSortingState
}) {
  const { id }: { id: string } = useParams()
  const router = useRouter()
  const [dateRange, setDateRange] = useState<DateRange | undefined>()

  const [succeeded, setSucceeded] = useQueryState(
    'succeeded',
    parseAsString.withDefault('all'),
  )
  const [httpCodeClass, setHttpCodeClass] = useQueryState(
    'httpCodeClass',
    parseAsString.withDefault('all'),
  )
  const [eventTypes, setEventTypes] = useQueryState(
    'eventTypes',
    parseAsArrayOf(parseAsString).withDefault([]),
  )
  const [query, setQuery] = useQueryState(
    'query',
    parseAsString.withDefault(''),
  )

  const { data: endpoint } = useWebhookEndpoint(id)

  // ── Toggle Enabled ──

  const editWebhookEndpoint = useEditWebhookEndpoint()
  const handleToggleEnabled = useCallback(
    async (enabled: boolean) => {
      if (!endpoint) return
      try {
        const { error } = await editWebhookEndpoint.mutateAsync({
          id: endpoint.id,
          body: { enabled },
        })
        if (error) {
          toast({
            title: 'Webhook Endpoint Update Failed',
            description: `Error updating Webhook Endpoint: ${error.detail}`,
          })
          return
        }

        toast({
          title: enabled
            ? 'Webhook Endpoint Enabled'
            : 'Webhook Endpoint Disabled',
          description: enabled
            ? 'Webhook endpoint will now receive events'
            : 'Webhook endpoint will no longer receive events',
        })
      } catch {
        toast({
          title: 'Webhook Endpoint Update Failed',
          description: 'A network error occurred. Please try again.',
        })
      }
    },
    [editWebhookEndpoint, endpoint],
  )

  // ── Reset Secret ──

  const {
    hide: hideResetModal,
    isShown: isResetModalShown,
    show: showResetModal,
  } = useModal()
  const resetSecretWebhookEndpoint = useResetSecretWebhookEndpoint()
  const handleResetSecret = useCallback(async () => {
    if (!endpoint) return
    try {
      const { error } = await resetSecretWebhookEndpoint.mutateAsync({
        id: endpoint.id,
      })
      if (error) {
        toast({
          title: 'Webhook Secret Reset Failed',
          description: `Error resetting Webhook Secret: ${error.detail}`,
        })
        return
      }

      hideResetModal()
      toast({
        title: 'Webhook Secret Reset',
        description: 'Webhook Secret was reset successfully',
      })
    } catch {
      toast({
        title: 'Webhook Secret Reset Failed',
        description: 'A network error occurred. Please try again.',
      })
    }
  }, [resetSecretWebhookEndpoint, hideResetModal, endpoint])

  // ── Delete Endpoint ──

  const {
    hide: hideDeleteModal,
    isShown: isArchiveModalShown,
    show: showArchiveModal,
  } = useModal()
  const deleteWebhookEndpoint = useDeleteWebhookEndpoint()
  const handleDeleteWebhookEndpoint = useCallback(async () => {
    if (!endpoint) return

    try {
      const { error } = await deleteWebhookEndpoint.mutateAsync({
        id: endpoint.id,
      })

      if (error) {
        toast({
          title: 'Webhook Endpoint Deletion Failed',
          description: `Error deleting Webhook Endpoint: ${error.detail}`,
        })
        return
      }

      hideDeleteModal()

      router.push(
        getStatusRedirect(
          `/dashboard/${workspace.slug}/settings/webhooks`,
          'Webhook Endpoint Deleted',
          'Webhook Endpoint was deleted successfully',
        ),
      )
    } catch {
      toast({
        title: 'Webhook Endpoint Deletion Failed',
        description: 'A network error occurred. Please try again.',
      })
    }
  }, [deleteWebhookEndpoint, hideDeleteModal, router, endpoint, workspace])

  if (!endpoint) {
    return null
  }

  // ── Render ──

  return (
    <DashboardBody
      title="Webhook"
      header={
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={showResetModal}>
            Reset Secret
          </Button>
          <Button variant="destructive" onClick={showArchiveModal}>
            Delete
          </Button>
        </div>
      }
      contextView={<WebhookContextView endpoint={endpoint} />}
      className="gap-y-8"
      wide
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-lg">{endpoint.url}</h3>
          <div className="flex items-center gap-2">
            <span
              className="text-sm text-slate-500 dark:text-slate-400"
              id="webhook-status-label"
            >
              {endpoint.enabled ? 'Enabled' : 'Disabled'}
            </span>
            <Switch
              checked={endpoint.enabled}
              onCheckedChange={handleToggleEnabled}
              aria-labelledby="webhook-status-label"
            />
          </div>
        </div>
        <CopyToClipboardInput
          value={endpoint.secret}
          buttonLabel="Copy Secret"
        />
      </div>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-4">
          <h2 className="text-xl font-medium">Deliveries</h2>
          <WebhookFilter
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            succeeded={succeeded}
            onSucceededChange={(value) => setSucceeded(value)}
            httpCodeClass={httpCodeClass}
            onHttpCodeClassChange={(value) => setHttpCodeClass(value)}
            eventTypes={eventTypes}
            onEventTypesChange={setEventTypes}
            query={query}
            onQueryChange={setQuery}
          />
        </div>
        <DeliveriesTable
          endpoint={endpoint}
          pagination={pagination}
          sorting={sorting}
          workspace={workspace}
          dateRange={dateRange}
          succeeded={succeeded !== 'all' ? succeeded === 'true' : undefined}
          httpCodeClass={
            httpCodeClass !== 'all'
              ? (httpCodeClass as NonNullable<
                  operations['webhooks:list_webhook_deliveries']['parameters']['query']
                >['http_code_class'])
              : undefined
          }
          eventTypes={
            (eventTypes.length > 0 ? eventTypes : undefined) as NonNullable<
              operations['webhooks:list_webhook_deliveries']['parameters']['query']
            >['event_type']
          }
          query={query || undefined}
        />
      </div>

      <ConfirmModal
        title="Reset Webhook Secret"
        description={
          'This action will reset the webhook secret and invalidate the previous one. Are you sure you want to continue?'
        }
        destructiveText="Reset Secret"
        onConfirm={handleResetSecret}
        isShown={isResetModalShown}
        hide={hideResetModal}
      />
      <ConfirmModal
        title="Delete Webhook Endpoint"
        description={
          'This action will delete the endpoint configuration and stop sending webhooks to it'
        }
        destructiveText="Delete"
        onConfirm={handleDeleteWebhookEndpoint}
        isShown={isArchiveModalShown}
        hide={hideDeleteModal}
        destructive
      />
    </DashboardBody>
  )
}

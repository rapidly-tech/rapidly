'use client'

import {
  SettingsGroup,
  SettingsGroupActions,
} from '@/components/Settings/SettingsGroup'
import { useListWebhooksEndpoints } from '@/hooks/api'
import { CONFIG } from '@/utils/config'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import FormattedDateTime from '@rapidly-tech/ui/components/data/FormattedDateTime'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'
import { InlineModal } from '../../Modal/InlineModal'
import { useModal } from '../../Modal/useModal'
import NewWebhookModal from './NewWebhookModal'

/** Lists configured webhook endpoints with creation modal and links to endpoint detail pages. */
const WebhookSettings = (props: { workspace: schemas['Workspace'] }) => {
  const {
    isShown: isNewWebhookModalShown,
    show: showNewWebhookModal,
    hide: hideNewWebhookModal,
  } = useModal()

  const endpoints = useListWebhooksEndpoints({
    workspaceId: props.workspace.id,
    limit: 100,
    page: 1,
  })

  return (
    <>
      <SettingsGroup>
        {endpoints.data?.data && endpoints.data.data.length > 0 ? (
          endpoints.data?.data.map((e) => {
            return (
              <SettingsGroupActions key={e.id}>
                <Endpoint workspace={props.workspace} endpoint={e} />
              </SettingsGroupActions>
            )
          })
        ) : (
          <SettingsGroupActions>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {props.workspace.name} doesn&apos;t have any webhooks yet
            </p>
          </SettingsGroupActions>
        )}
        <SettingsGroupActions>
          <div className="flex flex-row items-center gap-x-4">
            <Button asChild onClick={showNewWebhookModal}>
              Add Endpoint
            </Button>
            <Link
              href={`${CONFIG.DOCS_BASE_URL}/integrate/webhooks/endpoints`}
              className="shrink-0"
            >
              <Button className="gap-x-1" asChild variant="ghost">
                <span>Documentation</span>
                <Icon icon="solar:arrow-right-up-linear" className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </SettingsGroupActions>
      </SettingsGroup>
      <InlineModal
        isShown={isNewWebhookModalShown}
        hide={hideNewWebhookModal}
        modalContent={
          <NewWebhookModal
            hide={hideNewWebhookModal}
            workspace={props.workspace}
          />
        }
      />
    </>
  )
}

export default WebhookSettings

const Endpoint = ({
  workspace,
  endpoint,
}: {
  workspace: schemas['Workspace']
  endpoint: schemas['WebhookEndpoint']
}) => {
  return (
    <div className="flex items-center justify-between overflow-hidden">
      <div className="flex w-2/3 flex-col gap-y-1">
        <p className="truncate font-mono text-sm">{endpoint.url}</p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          <FormattedDateTime datetime={endpoint.created_at} dateStyle="long" />
        </p>
      </div>
      <div className="text-slate-500 dark:text-slate-400">
        <Link
          href={`/dashboard/${workspace.slug}/settings/webhooks/endpoints/${endpoint.id}`}
        >
          <Button asChild variant="secondary">
            Details
          </Button>
        </Link>
      </div>
    </div>
  )
}

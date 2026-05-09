'use client'

import { useDeleteWorkspace } from '@/hooks/api'
import { TOAST_LONG_DURATION_MS } from '@/utils/constants/timings'
import { ROUTES } from '@/utils/routes'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { useRouter } from 'next/navigation'
import { useCallback, useState } from 'react'
import { ConfirmModal } from '../Modal/ConfirmModal'
import { toast } from '../Toast/use-toast'
import { SettingsGroup, SettingsGroupItem } from './SettingsGroup'

interface WorkspaceDeleteSettingsProps {
  workspace: schemas['Workspace']
}

/** Renders the workspace deletion settings with a confirmation modal and safety checks. */
export default function WorkspaceDeleteSettings({
  workspace,
}: WorkspaceDeleteSettingsProps) {
  const router = useRouter()
  const deleteWorkspace = useDeleteWorkspace()
  const [showDeleteModal, setShowDeleteModal] = useState(false)

  const handleDelete = useCallback(async () => {
    const { data, error } = await deleteWorkspace.mutateAsync({
      id: workspace.id,
    })

    if (error) {
      toast({
        title: 'Deletion Failed',
        description: error.detail as string,
        variant: 'error',
        duration: TOAST_LONG_DURATION_MS,
      })
      return
    }

    if (data.deleted) {
      toast({
        title: 'Workspace Deleted',
        description: 'Your workspace has been successfully deleted.',
        variant: 'success',
        duration: TOAST_LONG_DURATION_MS,
      })
      router.push(ROUTES.DASHBOARD.ROOT)
    } else if (data.requires_support) {
      const reasons = (data.blocked_reasons ?? [])
        .map((r: string) => {
          switch (r) {
            case 'stripe_account_deletion_failed':
              return 'Stripe account could not be deleted'
            default:
              return r
          }
        })
        .join(', ')

      toast({
        title: 'Deletion Request Submitted',
        description: `Your workspace ${reasons ? `(${reasons})` : ''} requires manual review. A support ticket has been created and our team will process your request.`,
        duration: TOAST_LONG_DURATION_MS,
      })
      setShowDeleteModal(false)
    }
  }, [deleteWorkspace, workspace.id, router])

  return (
    <>
      <SettingsGroup>
        <SettingsGroupItem
          title="Delete Workspace"
          description="Permanently delete this workspace and all associated data. This action cannot be undone."
        >
          <Button
            variant="destructive"
            onClick={() => setShowDeleteModal(true)}
            size="sm"
          >
            Delete
          </Button>
        </SettingsGroupItem>
      </SettingsGroup>

      <ConfirmModal
        isShown={showDeleteModal}
        hide={() => setShowDeleteModal(false)}
        title="Delete Workspace"
        description={`Are you sure you want to delete "${workspace.name}"? This action cannot be undone.`}
        body={
          <div className="text-sm text-slate-600 dark:text-slate-400">
            <p className="mb-2">When you delete an workspace:</p>
            <ul className="list-inside list-disc space-y-1">
              <li>Workspace data will be anonymized and marked as deleted</li>
              <li>
                If you have payments or active file shares, a support ticket
                will be created for manual review
              </li>
              <li>
                Connected Stripe account will be deleted if no blocking
                conditions exist
              </li>
            </ul>
          </div>
        }
        onConfirm={handleDelete}
        destructive
        destructiveText="Delete"
        confirmPrompt={workspace.slug}
      />
    </>
  )
}

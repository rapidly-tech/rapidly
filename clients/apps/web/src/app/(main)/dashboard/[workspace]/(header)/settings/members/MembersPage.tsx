'use client'

import { DashboardBody } from '@/components/Layout/DashboardLayout'
import { Modal } from '@/components/Modal'
import { ConfirmModal } from '@/components/Modal/ConfirmModal'
import { useModal } from '@/components/Modal/useModal'
import { useToast } from '@/components/Toast/use-toast'
import {
  useInviteWorkspaceMember,
  useLeaveWorkspace,
  useListWorkspaceMembers,
  useRemoveWorkspaceMember,
} from '@/hooks/api/org'
import { useAuth } from '@/hooks/auth'
import { ROUTES } from '@/utils/routes'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Avatar from '@rapidly-tech/ui/components/data/Avatar'
import {
  DataTable,
  DataTableColumnDef,
  DataTableColumnHeader,
} from '@rapidly-tech/ui/components/data/DataTable'
import FormattedDateTime from '@rapidly-tech/ui/components/data/FormattedDateTime'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import { useRouter } from 'next/navigation'
import { useCallback, useMemo, useState } from 'react'

// ── Main Component ──

export default function ClientPage({
  workspace,
}: {
  workspace: schemas['Workspace']
}) {
  const router = useRouter()
  const { currentUser } = useAuth()
  const { toast } = useToast()
  const { data: members, isLoading } = useListWorkspaceMembers(workspace.id)
  const {
    show: openInviteMemberModal,
    hide: hideInviteMemberModal,
    isShown: isInviteMemberModalShown,
  } = useModal()

  // ── Modal State ──

  const [memberToRemove, setMemberToRemove] = useState<
    schemas['WorkspaceMember'] | null
  >(null)
  const {
    show: showRemoveModal,
    hide: hideRemoveModal,
    isShown: isRemoveModalShown,
  } = useModal()

  // Leave workspace modal state
  const {
    show: showLeaveModal,
    hide: hideLeaveModal,
    isShown: isLeaveModalShown,
  } = useModal()

  const removeMember = useRemoveWorkspaceMember(workspace.id)
  const leaveWorkspace = useLeaveWorkspace(workspace.id)

  // ── Member Actions ──
  const adminMember = useMemo(
    () => members?.data.find((m) => m.is_admin),
    [members],
  )
  const isCurrentUserAdmin = adminMember?.user_id === currentUser?.id

  const handleRemoveMember = useCallback(
    (member: schemas['WorkspaceMember']) => {
      setMemberToRemove(member)
      showRemoveModal()
    },
    [showRemoveModal],
  )

  const onConfirmRemove = useCallback(async () => {
    if (!memberToRemove) return

    try {
      await removeMember.mutateAsync(memberToRemove.user_id)
      toast({
        title: 'Member removed',
        description: `${memberToRemove.email} has been removed from the workspace.`,
      })
    } catch {
      toast({
        title: 'Failed to remove member',
        description: 'Please try again.',
      })
    }
  }, [memberToRemove, removeMember, toast])

  const onConfirmLeave = useCallback(async () => {
    try {
      await leaveWorkspace.mutateAsync()
      toast({
        title: 'Left workspace',
        description: `You have left ${workspace.name}.`,
      })
      router.push(ROUTES.DASHBOARD.ROOT)
    } catch {
      toast({
        title: 'Failed to leave workspace',
        description: 'Please try again.',
      })
    }
  }, [leaveWorkspace, workspace.name, router, toast])

  // ── Table Columns ──

  const columns: DataTableColumnDef<schemas['WorkspaceMember']>[] = [
    {
      id: 'member',
      accessorKey: 'email',
      enableSorting: true,
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="User" />
      ),
      cell: ({ row: { original: member } }) => {
        const isCurrentUser = member.user_id === currentUser?.id
        return (
          <div className="flex flex-row items-center gap-2">
            <Avatar avatar_url={member.avatar_url} name={member.email} />
            <span className="fw-medium truncate">{member.email}</span>
            {member.is_admin && (
              <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-500">
                Admin
              </span>
            )}
            {isCurrentUser && (
              <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-500">
                You
              </span>
            )}
          </div>
        )
      },
    },
    {
      accessorKey: 'created_at',
      enableSorting: true,
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Joined on" />
      ),
      cell: ({ row: { original: member } }) => {
        return <FormattedDateTime datetime={member.created_at} />
      },
    },
    {
      id: 'actions',
      header: () => null,
      cell: ({ row: { original: member } }) => {
        const isCurrentUser = member.user_id === currentUser?.id
        const isMemberAdmin = member.is_admin

        // Admin cannot remove themselves
        if (isCurrentUserAdmin && isMemberAdmin) {
          return null
        }

        // Admin can remove other members
        if (isCurrentUserAdmin && !isMemberAdmin) {
          return (
            <div className="flex justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleRemoveMember(member)}
              >
                Remove
              </Button>
            </div>
          )
        }

        // Non-admin can only leave (their own row)
        if (!isCurrentUserAdmin && isCurrentUser) {
          return (
            <div className="flex justify-end">
              <Button variant="ghost" size="sm" onClick={showLeaveModal}>
                Leave
              </Button>
            </div>
          )
        }

        return null
      },
    },
  ]

  return (
    <DashboardBody
      wrapperClassName="max-w-(--breakpoint-sm)!"
      className="flex flex-col gap-y-8"
      title="Settings"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium">Members</h2>
        <Button onClick={openInviteMemberModal} variant="default">
          <Icon icon="solar:add-circle-linear" className="mr-2 h-4 w-4" />
          <span>Invite</span>
        </Button>
      </div>
      <p className="text-slate-500 dark:text-slate-400">
        Manage users who have access to this workspace. All members are entitled
        to view and manage workspace settings, file shares, earnings, etc.
      </p>

      {members && (
        <DataTable
          columns={columns}
          data={members.data}
          isLoading={isLoading}
          wrapperClassName="glass-elevated rounded-2xl bg-slate-50 shadow-xs lg:rounded-3xl dark:bg-slate-900 border-0"
        />
      )}

      <Modal
        title="Invite Member"
        className="max-w-(--breakpoint-sm)!"
        modalContent={
          <InviteMemberModal
            workspaceId={workspace.id}
            onClose={hideInviteMemberModal}
          />
        }
        isShown={isInviteMemberModalShown}
        hide={hideInviteMemberModal}
      />

      <ConfirmModal
        isShown={isRemoveModalShown}
        hide={hideRemoveModal}
        onConfirm={onConfirmRemove}
        title="Remove Member"
        description={`Are you sure you want to remove ${memberToRemove?.email} from this workspace?`}
        destructive
        destructiveText="Remove"
      />

      <ConfirmModal
        isShown={isLeaveModalShown}
        hide={hideLeaveModal}
        onConfirm={onConfirmLeave}
        title="Leave Workspace"
        description={`Are you sure you want to leave ${workspace.name}? You will lose access to this workspace.`}
        destructive
        destructiveText="Leave"
      />
    </DashboardBody>
  )
}

// ── Invite Member Modal ──

function InviteMemberModal({
  workspaceId,
  onClose,
}: {
  workspaceId: string
  onClose: () => void
}) {
  const { toast } = useToast()
  const [email, setEmail] = useState('')
  const inviteMember = useInviteWorkspaceMember(workspaceId)

  const handleInvite = async () => {
    if (!email) return

    try {
      const result = await inviteMember.mutateAsync(email)
      if (result.response.status == 200) {
        toast({
          title: 'Member already added',
          description: 'User is already a member of this workspace',
        })
      } else if (result.data) {
        toast({
          title: 'Member added',
          description: 'User successfully added to workspace',
        })
        onClose()
      } else if (result.error) {
        toast({
          title: 'Invite failed',
          description: 'Failed to invite user. Please try again.',
        })
      }
    } catch {
      toast({
        title: 'Invite failed',
        description: 'Failed to invite user. Please try again.',
      })
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    handleInvite()
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full flex-col gap-y-6 p-8">
      <h3 className="text-lg font-medium">Invite User</h3>
      <Input
        type="email"
        placeholder="Enter email address"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        autoFocus
      />
      <div className="flex gap-2">
        <Button
          type="submit"
          disabled={!email || inviteMember.isPending}
          loading={inviteMember.isPending}
        >
          Send Invite
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

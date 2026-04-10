'use client'

import revalidate from '@/app/actions'
import SupportedUseCases from '@/components/Onboarding/components/SupportedUseCases'
import { useAuth } from '@/hooks'
import { useCreateWorkspace } from '@/hooks/api'
import { resolveApiUrl } from '@/utils/api'
import { setValidationErrors } from '@/utils/api/errors'
import { CONFIG } from '@/utils/config'
import { schemas } from '@rapidly-tech/client'
import Avatar from '@rapidly-tech/ui/components/data/Avatar'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import { Checkbox } from '@rapidly-tech/ui/components/primitives/checkbox'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { Label } from '@rapidly-tech/ui/components/primitives/label'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import slugify from 'slugify'
import SharedLayout from './components/SharedLayout'

// ── Main Component ──

const WorkspaceSelectionPage = ({
  authorizeResponse: { client, workspaces },
  searchParams,
}: {
  authorizeResponse: schemas['AuthorizeResponseWorkspace']
  searchParams: Record<string, string>
}) => {
  const router = useRouter()
  const { currentUser, setWorkspaceMemberships } = useAuth()
  const createWorkspace = useCreateWorkspace()
  const [editedSlug, setEditedSlug] = useState(false)

  const form = useForm<{
    name: string
    slug: string
    terms: boolean
  }>({
    defaultValues: {
      name: '',
      slug: '',
      terms: false,
    },
  })

  const {
    control,
    handleSubmit,
    watch,
    setError,
    setValue,
    formState: { errors },
  } = form

  const name = watch('name')
  const slug = watch('slug')
  const terms = watch('terms')

  // ── Slug Auto-generation ──

  useEffect(() => {
    if (!editedSlug && name) {
      setValue('slug', slugify(name, { lower: true, strict: true }))
    } else if (slug) {
      setValue(
        'slug',
        slugify(slug, { lower: true, trim: false, strict: true }),
      )
    }
  }, [name, editedSlug, slug, setValue])

  // ── URL Helpers ──

  const serializedSearchParams = new URLSearchParams(searchParams).toString()
  const actionURL = `${resolveApiUrl()}/api/oauth2/consent?${serializedSearchParams}`

  const buildWorkspaceSelectionURL = (
    workspace: schemas['AuthorizeWorkspace'],
  ) => {
    const updatedSearchParams = {
      ...searchParams,
      sub: workspace.id,
    }
    const serializedSearchParams = new URLSearchParams(
      updatedSearchParams,
    ).toString()
    return `?${serializedSearchParams}`
  }

  // ── Form Submission ──

  const onSubmit = async (data: {
    name: string
    slug: string
    terms: boolean
  }) => {
    if (!data.terms) return

    const { data: workspace, error } = await createWorkspace.mutateAsync({
      name: data.name,
      slug: data.slug,
      default_presentment_currency: 'usd',
    })

    if (error) {
      if (error.detail) {
        setValidationErrors(error.detail, setError)
      }
      return
    }

    await revalidate(`users:${currentUser?.id}:workspaces`, {
      expire: 0,
    })
    setWorkspaceMemberships((orgs) => [...orgs, workspace])

    // Navigate to the same page with the new workspace selected
    const updatedSearchParams = new URLSearchParams({
      ...searchParams,
      sub: workspace.id,
    })
    router.push(`?${updatedSearchParams.toString()}`)
  }

  const clientName = client.client_name || client.client_id
  const hasTerms = client.policy_uri || client.tos_uri
  const hasWorkspaces = workspaces.length > 0

  // ── Render: No Workspaces ──
  if (!hasWorkspaces) {
    return (
      <SharedLayout
        client={client}
        introduction={
          <>
            Welcome to Rapidly!
            <br />
            Create an workspace and connect to{' '}
            <span className="font-medium text-slate-700 dark:text-slate-400">
              {clientName}
            </span>
            .
          </>
        }
      >
        <Form {...form}>
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="flex flex-col gap-y-6 lg:-mx-16"
            id="workspace-create-form"
          >
            <div className="glass-card flex flex-col gap-y-4 rounded-2xl p-6">
              <FormField
                control={control}
                name="name"
                rules={{
                  required: 'Workspace name is required',
                  minLength: {
                    value: 3,
                    message: 'Name must be at least 3 characters',
                  },
                }}
                render={({ field }) => (
                  <FormItem className="w-full">
                    <FormControl className="flex w-full flex-col gap-y-4">
                      <Label htmlFor="name">Workspace Name</Label>
                      <Input {...field} placeholder="Acme Inc." />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={control}
                name="slug"
                rules={{
                  required: 'Slug is required',
                  minLength: {
                    value: 3,
                    message: 'Slug must be at least 3 characters',
                  },
                }}
                render={({ field }) => (
                  <FormItem className="w-full">
                    <FormControl className="flex w-full flex-col gap-y-4">
                      <Label htmlFor="slug">Workspace Slug</Label>
                      <Input
                        type="text"
                        {...field}
                        placeholder="acme-inc"
                        onFocus={() => setEditedSlug(true)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="glass-card flex flex-col gap-y-4 rounded-2xl p-6">
              <SupportedUseCases />
            </div>

            <div className="glass-card gap-y- flex flex-col rounded-2xl p-6">
              <FormField
                control={control}
                name="terms"
                rules={{
                  required: 'You must accept the terms to continue',
                }}
                render={({ field }) => (
                  <FormItem>
                    <div className="flex flex-row items-start gap-x-3">
                      <Checkbox
                        id="terms"
                        checked={field.value}
                        onCheckedChange={(checked) => {
                          setValue('terms', checked === true)
                        }}
                        className="mt-1"
                      />
                      <div className="flex flex-col gap-y-2 text-sm">
                        <label
                          htmlFor="terms"
                          className="cursor-pointer leading-relaxed font-medium"
                        >
                          I understand the restrictions above and agree to
                          Rapidly&rsquo;s terms
                        </label>
                        <ul className="flex flex-col gap-y-1 text-sm text-slate-500 dark:text-slate-400">
                          <li>
                            <a
                              href={`${CONFIG.DOCS_BASE_URL}/account-reviews`}
                              className="text-slate-600 hover:underline dark:text-slate-400"
                              target="_blank"
                              rel="noreferrer"
                            >
                              Account Reviews Policy
                            </a>
                            {' - '}I&apos;ll comply with KYC/AML requirements
                            including website and social verification
                          </li>
                          <li>
                            <a
                              href={CONFIG.LEGAL_TERMS_URL}
                              className="text-slate-600 hover:underline dark:text-slate-400"
                              target="_blank"
                              rel="noreferrer"
                            >
                              Terms of Service
                            </a>
                          </li>
                          <li>
                            <a
                              href={CONFIG.LEGAL_PRIVACY_URL}
                              className="text-slate-600 hover:underline dark:text-slate-400"
                              target="_blank"
                              rel="noreferrer"
                            >
                              Privacy Policy
                            </a>
                          </li>
                        </ul>
                      </div>
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {errors.root && (
              <p className="text-destructive-foreground text-sm">
                {errors.root.message}
              </p>
            )}
          </form>
        </Form>

        <div className="flex flex-col gap-y-3">
          <Button
            type="submit"
            loading={createWorkspace.isPending}
            disabled={name.length < 3 || slug.length < 3 || !terms}
            form="workspace-create-form"
          >
            Create Workspace
          </Button>
          <form method="post" action={actionURL}>
            <Button
              variant="secondary"
              className="w-full"
              type="submit"
              name="action"
              value="deny"
            >
              Deny
            </Button>
          </form>
        </div>

        {hasTerms && (
          <div className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
            Before using this app, you can review {clientName}&apos;s{' '}
            {client.tos_uri && (
              <a
                className="text-slate-700 dark:text-slate-500"
                href={client.tos_uri}
              >
                Terms of Service
              </a>
            )}
            {client.tos_uri && client.policy_uri && ' and '}
            {client.policy_uri && (
              <a
                className="text-slate-700 dark:text-slate-500"
                href={client.policy_uri}
              >
                Privacy Policy
              </a>
            )}
            .
          </div>
        )}
      </SharedLayout>
    )
  }

  // ── Render: Workspace Selection ──

  return (
    <SharedLayout
      client={client}
      introduction={
        <>
          <span className="font-medium text-slate-700 dark:text-slate-400">
            {clientName}
          </span>{' '}
          wants to access one of your Rapidly workspaces. Select one:
        </>
      }
    >
      <form method="post" action={actionURL}>
        <div className="mb-6 flex w-full flex-col gap-3">
          {workspaces.map((workspace) => (
            <Link
              key={workspace.id}
              href={buildWorkspaceSelectionURL(workspace)}
            >
              <div className="glass-card flex w-full flex-row items-center gap-2 rounded-2xl px-2.5 py-3 text-sm transition-colors hover:bg-white/20">
                <Avatar
                  className="h-8 w-8"
                  avatar_url={workspace.avatar_url}
                  name={workspace.slug}
                />
                {workspace.slug}
              </div>
            </Link>
          ))}
        </div>
        <div className="grid w-full">
          <Button
            variant="secondary"
            className="grow"
            type="submit"
            name="action"
            value="deny"
          >
            Deny
          </Button>
        </div>
        {hasTerms && (
          <div className="mt-8 text-center text-sm text-slate-500 dark:text-slate-400">
            Before using this app, you can review {clientName}&apos;s{' '}
            {client.tos_uri && (
              <a
                className="text-slate-700 dark:text-slate-500"
                href={client.tos_uri}
              >
                Terms of Service
              </a>
            )}
            {client.tos_uri && client.policy_uri && ' and '}
            {client.policy_uri && (
              <a
                className="text-slate-700 dark:text-slate-500"
                href={client.policy_uri}
              >
                Privacy Policy
              </a>
            )}
            .
          </div>
        )}
      </form>
    </SharedLayout>
  )
}

export default WorkspaceSelectionPage

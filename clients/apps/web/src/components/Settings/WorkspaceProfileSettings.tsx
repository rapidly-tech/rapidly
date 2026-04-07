// ── Imports ──

import { useAuth } from '@/hooks'
import { useUpdateWorkspace } from '@/hooks/api'
import { useAutoSave } from '@/hooks/useAutoSave'
import { useURLValidation } from '@/hooks/useURLValidation'
import { setValidationErrors } from '@/utils/api/errors'
import { WORKSPACE_DESCRIPTION_MAX_CHARS } from '@/utils/constants/validation'
import { Icon } from '@iconify/react'
import { isValidationError, schemas } from '@rapidly-tech/client'
import Avatar from '@rapidly-tech/ui/components/data/Avatar'
import Button from '@rapidly-tech/ui/components/forms/Button'
import CopyToClipboardInput from '@rapidly-tech/ui/components/forms/CopyToClipboardInput'
import Input from '@rapidly-tech/ui/components/forms/Input'
import MoneyInput from '@rapidly-tech/ui/components/forms/MoneyInput'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@rapidly-tech/ui/components/forms/Select'
import TextArea from '@rapidly-tech/ui/components/forms/TextArea'
import { Checkbox } from '@rapidly-tech/ui/components/primitives/checkbox'
import {
  Form,
  FormControl,
  FormField,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { useRouter } from 'next/navigation'
import React, { useCallback } from 'react'
import { FileRejection } from 'react-dropzone'
import { useForm, useFormContext } from 'react-hook-form'
import { twMerge } from 'tailwind-merge'
import { FileObject, useFileUpload } from '../FileUpload'
import { toast } from '../Toast/use-toast'
import ConfirmationButton from '../ui/ConfirmationButton'
import {
  SettingsGroup,
  SettingsGroupActions,
  SettingsGroupItem,
} from './SettingsGroup'

// ── Types and Constants ──

interface WorkspaceDetailsFormProps {
  workspace: schemas['Workspace']
  inKYCMode: boolean
}

const AcquisitionOptions = {
  website: 'Website & SEO',
  socials: 'Social media',
  sales: 'Sales',
  ads: 'Ads',
  email: 'Email marketing',
  other: 'Other',
}

const SwitchingFromOptions = {
  dropbox: 'Dropbox',
  google_drive: 'Google Drive',
  wetransfer: 'WeTransfer',
  sharepoint: 'SharePoint',
  other: 'Other',
}

const SOCIAL_PLATFORM_DOMAINS = {
  'x.com': 'x',
  'twitter.com': 'x',
  'instagram.com': 'instagram',
  'facebook.com': 'facebook',
  'youtube.com': 'youtube',
  'linkedin.com': 'linkedin',
  'youtu.be': 'youtube',
  'github.com': 'github',
}

// ── Social Media Links ──

interface WorkspaceSocialLinksProps {
  required?: boolean
}

const WorkspaceSocialLinks = ({ required }: WorkspaceSocialLinksProps) => {
  const { watch, setValue, formState } =
    useFormContext<schemas['WorkspaceUpdate']>()
  const socials = watch('socials') || []

  const hasValidSocial = socials.some(
    (social) => social.url && social.url.trim() !== '',
  )
  const showError = required && formState.isSubmitted && !hasValidSocial

  const getIcon = (platform: string, className: string) => {
    const iconMap: Record<string, string> = {
      x: 'mdi:twitter',
      instagram: 'mdi:instagram',
      facebook: 'mdi:facebook',
      github: 'mdi:github',
      youtube: 'mdi:youtube',
      linkedin: 'mdi:linkedin',
    }
    const iconName = iconMap[platform] ?? 'solar:global-linear'
    return <Icon icon={iconName} className={className} />
  }

  const handleAddSocial = () => {
    setValue('socials', [...socials, { platform: 'other', url: '' }], {
      shouldDirty: true,
    })
  }

  const handleRemoveSocial = (index: number) => {
    setValue(
      'socials',
      socials.filter((_, i) => i !== index),
      { shouldDirty: true },
    )
  }

  const handleChange = (index: number, value: string) => {
    if (value.startsWith('http://')) {
      value = value.replace('http://', 'https://')
    }
    const hasProtocol = value.startsWith('https://')
    const isTypingProtocol =
      'https://'.startsWith(value) || 'http://'.startsWith(value)
    if (!hasProtocol && !isTypingProtocol) {
      value = 'https://' + value
    }

    // Infer the platform from the URL
    let newPlatform: schemas['WorkspaceSocialPlatforms'] = 'other'
    try {
      const url = new URL(value)
      const hostname = url.hostname as keyof typeof SOCIAL_PLATFORM_DOMAINS
      newPlatform = (SOCIAL_PLATFORM_DOMAINS[hostname] ??
        'other') as schemas['WorkspaceSocialPlatforms']
    } catch {
      // ignore
    }

    // Update the socials array
    const updatedSocials = [...socials]
    updatedSocials[index] = { platform: newPlatform, url: value }
    setValue('socials', updatedSocials, { shouldDirty: true })
  }

  return (
    <div className="space-y-3">
      {socials.map((social, index) => (
        <div
          key={`${social.platform}-${index}`}
          className="flex items-center gap-3"
        >
          <div className="flex w-5 justify-center">
            {getIcon(
              social.platform,
              'text-slate-400 dark:text-slate-500 h-4 w-4',
            )}
          </div>
          <Input
            value={social.url || ''}
            onChange={(e) => handleChange(index, e.target.value)}
            placeholder="https://"
            className="flex-1"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => handleRemoveSocial(index)}
            className="text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-400"
          >
            <Icon icon="solar:close-circle-linear" className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        size="sm"
        variant="secondary"
        onClick={handleAddSocial}
      >
        <Icon icon="solar:add-circle-linear" className="mr-1 h-4 w-4" />
        Add Social
      </Button>
      {showError && (
        <p className="text-destructive text-sm font-medium">
          At least one social media link is required
        </p>
      )}
    </div>
  )
}

// ── Helper Components ──

const CompactTextArea = ({
  field,
  placeholder,
  rows = 3,
}: {
  field: {
    value: string | undefined
    onChange: (...event: unknown[]) => void
    onBlur: () => void
    name: string
  }
  placeholder: string
  rows?: number
}) => (
  <TextArea
    {...field}
    rows={rows}
    placeholder={placeholder}
    className="resize-none"
  />
)

// ── Workspace Details Form ──

export const WorkspaceDetailsForm: React.FC<WorkspaceDetailsFormProps> = ({
  workspace,
  inKYCMode,
}) => {
  const { control, watch, setError, setValue } =
    useFormContext<schemas['WorkspaceUpdate']>()
  const name = watch('name')
  const avatarURL = watch('avatar_url')
  const { status: urlStatus, validateURL } = useURLValidation({
    workspaceSlug: workspace.slug,
  })

  const onFilesUpdated = useCallback(
    (files: FileObject<schemas['WorkspaceAvatarFileRead']>[]) => {
      if (files.length === 0) {
        return
      }
      const lastFile = files[files.length - 1]
      setValue('avatar_url', lastFile.public_url, { shouldDirty: true })
    },
    [setValue],
  )
  const onFilesRejected = useCallback(
    (rejections: FileRejection[]) => {
      rejections.forEach((rejection) => {
        setError('avatar_url', { message: rejection.errors[0].message })
      })
    },
    [setError],
  )
  const { getRootProps, getInputProps, isDragActive } = useFileUpload({
    workspace: workspace,
    service: 'workspace_avatar',
    accept: {
      'image/jpeg': [],
      'image/png': [],
      'image/gif': [],
      'image/webp': [],
      'image/svg+xml': [],
    },
    maxSize: 1 * 1024 * 1024,
    onFilesUpdated,
    onFilesRejected,
    initialFiles: [],
  })

  return (
    <div className="space-y-8">
      {/* Basic Info - Always Visible */}
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-12">
          <div className="sm:col-span-2">
            <label className="mb-2 block text-sm font-medium">Logo</label>
            <FormField
              control={control}
              name="avatar_url"
              render={() => (
                <div>
                  <div
                    {...getRootProps()}
                    className={twMerge(
                      'relative cursor-pointer',
                      isDragActive && 'opacity-50',
                    )}
                  >
                    <input {...getInputProps()} />
                    <Avatar
                      avatar_url={avatarURL ?? ''}
                      name={name ?? ''}
                      className="h-16 w-16 transition-opacity hover:opacity-75"
                    />
                    <div className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity hover:opacity-100">
                      <Icon
                        icon="solar:gallery-add-linear"
                        className="h-5 w-5 text-slate-600 dark:text-slate-400"
                      />
                    </div>
                  </div>
                  <FormMessage className="mt-2 text-xs/snug" />
                </div>
              )}
            />
          </div>

          <div className="space-y-4 sm:col-span-10">
            <div>
              <label className="mb-2 block text-sm font-medium">
                Workspace Name *
              </label>
              <FormField
                control={control}
                name="name"
                rules={{ required: 'Workspace name is required' }}
                render={({ field }) => (
                  <div>
                    <Input
                      {...field}
                      value={field.value || ''}
                      placeholder="Acme Inc"
                    />
                    <FormMessage />
                  </div>
                )}
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Support Email *
              </label>
              <FormField
                control={control}
                name="email"
                rules={{ required: 'Support email is required' }}
                render={({ field }) => (
                  <div>
                    <Input
                      type="email"
                      {...field}
                      value={field.value || ''}
                      placeholder="support@acme.com"
                    />
                    <FormMessage />
                  </div>
                )}
              />
            </div>
          </div>
        </div>

        <div>
          <label className="mb-2 block text-sm font-medium">Website *</label>
          <FormField
            control={control}
            name="website"
            rules={{
              required: 'Website is required',
              validate: (value) => {
                if (!value) return 'Website is required'
                if (
                  !value.startsWith('https://') &&
                  !value.startsWith('http://')
                ) {
                  return 'Website must start with http:// or https://'
                }
                try {
                  new URL(value)
                  return true
                } catch {
                  return 'Please enter a valid URL'
                }
              },
            }}
            render={({ field }) => (
              <div>
                <Input
                  type="url"
                  {...field}
                  value={field.value || ''}
                  placeholder="https://acme.com"
                  onChange={(e) => {
                    let value = e.target.value
                    const hasProtocol =
                      value.startsWith('https://') ||
                      value.startsWith('http://')
                    const isTypingProtocol =
                      'https://'.startsWith(value) ||
                      'http://'.startsWith(value)
                    if (!hasProtocol && !isTypingProtocol) {
                      value = 'https://' + value
                    }
                    field.onChange(value)
                  }}
                  onBlur={(e) => {
                    field.onBlur()
                    validateURL(e.target.value)
                  }}
                  postSlot={
                    urlStatus === 'validating' ? (
                      <Icon
                        icon="solar:refresh-circle-linear"
                        className="h-4 w-4 animate-spin text-slate-400 dark:text-slate-500"
                      />
                    ) : urlStatus === 'valid' ? (
                      <Icon
                        icon="solar:check-circle-linear"
                        className="h-4 w-4 text-emerald-500"
                      />
                    ) : urlStatus === 'invalid' ? (
                      <Icon
                        icon="solar:danger-triangle-linear"
                        className="h-4 w-4 text-amber-500"
                      />
                    ) : null
                  }
                />
                <FormMessage />
                {urlStatus === 'invalid' && (
                  <p className="mt-1 text-xs text-amber-600">
                    Website appears to be unreachable
                  </p>
                )}
              </div>
            )}
          />
        </div>

        {/* Social Links - Progressive Disclosure */}
        <div>
          <div className="mb-4 flex flex-col items-start">
            <label className="block text-sm font-medium">
              Social Media {inKYCMode && '*'}
            </label>
          </div>
          <WorkspaceSocialLinks required={inKYCMode} />
        </div>
      </div>

      {/* Business Details - KYC Mode Only */}
      {inKYCMode && (
        <div className="border-t pt-8">
          <div className="mb-6">
            <h3 className="mb-2 text-lg font-medium">Business Details</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Help us understand your business for compliance and setup.
            </p>
          </div>

          <div className="space-y-6">
            <div>
              <label className="mb-2 block text-sm font-medium">
                Describe your business *
              </label>
              <p className="mb-2 text-xs text-slate-600 dark:text-slate-400">
                Tell us: what industry you&apos;re in, what problem you solve,
                and who your customers are
              </p>
              <FormField
                control={control}
                name="details.about"
                rules={{
                  required: 'Please describe your business',
                  minLength: {
                    value: 50,
                    message: 'Please provide at least 50 characters',
                  },
                  maxLength: {
                    value: WORKSPACE_DESCRIPTION_MAX_CHARS,
                    message: `Please keep under ${WORKSPACE_DESCRIPTION_MAX_CHARS} characters`,
                  },
                }}
                render={({ field }) => (
                  <div>
                    <CompactTextArea
                      field={field}
                      placeholder="We make project management software for design teams."
                    />
                    <div className="mt-1 flex items-center justify-between">
                      <FormMessage />
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        {field.value?.length || 0}/
                        {WORKSPACE_DESCRIPTION_MAX_CHARS} characters (min 50)
                      </span>
                    </div>
                  </div>
                )}
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                What types of files do you share? *
              </label>
              <p className="mb-2 text-xs text-slate-600 dark:text-slate-400">
                Tell us: file types, typical sizes, and how recipients use them
              </p>
              <FormField
                control={control}
                name="details.product_description"
                rules={{
                  required: 'Please describe what you share',
                  minLength: {
                    value: 50,
                    message: 'Please provide at least 50 characters',
                  },
                  maxLength: {
                    value: WORKSPACE_DESCRIPTION_MAX_CHARS,
                    message: `Please keep under ${WORKSPACE_DESCRIPTION_MAX_CHARS} characters`,
                  },
                }}
                render={({ field }) => (
                  <div>
                    <CompactTextArea
                      field={field}
                      placeholder="Design assets, client deliverables, and project documentation. Typical files are 10-500MB including PSD, PDF, and ZIP archives."
                    />
                    <div className="mt-1 flex items-center justify-between">
                      <FormMessage />
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        {field.value?.length || 0}/
                        {WORKSPACE_DESCRIPTION_MAX_CHARS} characters (min 50)
                      </span>
                    </div>
                  </div>
                )}
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                How will you use Rapidly for your business? *
              </label>
              <p className="mb-2 text-xs text-slate-600 dark:text-slate-400">
                Tell us: how you plan to use Rapidly, what features you&apos;ll
                use, and how it fits your workflow
              </p>
              <FormField
                control={control}
                name="details.intended_use"
                rules={{
                  required: 'Please describe how you will use Rapidly',
                  minLength: {
                    value: 30,
                    message: 'Please provide at least 30 characters',
                  },
                  maxLength: {
                    value: WORKSPACE_DESCRIPTION_MAX_CHARS,
                    message: `Please keep under ${WORKSPACE_DESCRIPTION_MAX_CHARS} characters`,
                  },
                }}
                render={({ field }) => (
                  <div>
                    <CompactTextArea
                      field={field}
                      placeholder="Sharing client deliverables via branded pages, API for automated file distribution, webhooks for download tracking"
                    />
                    <div className="mt-1 flex items-center justify-between">
                      <FormMessage />
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        {field.value?.length || 0}/
                        {WORKSPACE_DESCRIPTION_MAX_CHARS} characters (min 30)
                      </span>
                    </div>
                  </div>
                )}
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Main customer acquisition channels *
              </label>
              <FormField
                control={control}
                name="details.customer_acquisition"
                rules={{
                  required: 'Please select at least one acquisition channel',
                  validate: (value) =>
                    (value && value.length > 0) ||
                    'Please select at least one channel',
                }}
                render={({ field }) => (
                  <div>
                    <div className="space-y-2">
                      {Object.entries(AcquisitionOptions).map(
                        ([key, label]) => (
                          <label
                            key={key}
                            className="flex cursor-pointer items-center gap-2"
                          >
                            <Checkbox
                              checked={field.value?.includes(key) || false}
                              onCheckedChange={(checked) => {
                                const current = field.value || []
                                if (checked) {
                                  field.onChange([...current, key])
                                } else {
                                  field.onChange(
                                    current.filter((v) => v !== key),
                                  )
                                }
                              }}
                            />
                            <span className="text-sm">{label}</span>
                          </label>
                        ),
                      )}
                    </div>
                    <FormMessage className="mt-2" />
                  </div>
                )}
              />
            </div>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium">
                  Expected annual revenue *
                </label>
                <FormField
                  control={control}
                  name="details.future_annual_revenue"
                  render={({ field }) => (
                    <div>
                      <MoneyInput
                        {...field}
                        placeholder={100_000_000}
                        currency="usd"
                        className="w-full"
                      />
                      <FormMessage />
                    </div>
                  )}
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">
                  Currently using
                </label>
                <FormField
                  control={control}
                  name="details.switching_from"
                  render={({ field }) => (
                    <div>
                      <Select
                        value={field.value || 'none'}
                        onValueChange={(value) => {
                          field.onChange(value === 'none' ? undefined : value)
                          setValue('details.switching', value !== 'none', {
                            shouldDirty: true,
                          })
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select a platform" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">
                            This is my first file sharing platform
                          </SelectItem>
                          {Object.entries(SwitchingFromOptions).map(
                            ([key, label]) => (
                              <SelectItem key={key} value={key}>
                                {label}
                              </SelectItem>
                            ),
                          )}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </div>
                  )}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Component ──

interface WorkspaceProfileSettingsProps {
  workspace: schemas['Workspace']
  kyc?: boolean
  onSubmitted?: () => void
}

/** Renders the workspace profile settings form with avatar upload, social links, and KYC business details. */
const WorkspaceProfileSettings: React.FC<WorkspaceProfileSettingsProps> = ({
  workspace,
  kyc,
  onSubmitted,
}) => {
  const router = useRouter()
  const form = useForm<schemas['WorkspaceUpdate']>({
    defaultValues: workspace,
  })
  const { handleSubmit, setError, formState, reset } = form
  const inKYCMode = kyc === true

  const { currentUser } = useAuth()

  const updateWorkspace = useUpdateWorkspace()

  const onSave = async (body: schemas['WorkspaceUpdate']) => {
    const emptySocials =
      body.socials?.filter(
        (social) => !social.url || social.url.trim() === '',
      ) || []
    const cleanedBody = {
      ...body,
      socials: body.socials?.filter(
        (social) => social.url && social.url.trim() !== '',
      ),
    }

    const { data, error } = await updateWorkspace.mutateAsync({
      id: workspace.id,
      body: cleanedBody,
      userId: currentUser?.id,
    })

    if (error) {
      const errorMessage = Array.isArray(error.detail)
        ? error.detail[0]?.msg ||
          'An error occurred while updating the workspace'
        : typeof error.detail === 'string'
          ? error.detail
          : 'An error occurred while updating the workspace'

      if (isValidationError(error.detail)) {
        setValidationErrors(error.detail, setError)
      } else {
        setError('root', { message: errorMessage })
      }

      toast({
        title: 'Workspace Update Failed',
        description: errorMessage,
      })

      return
    }

    reset({
      ...data,
      socials: [...(data.socials || []), ...emptySocials],
    })

    // Refresh the router to get the updated workspace data from the server
    router.refresh()

    if (onSubmitted) {
      onSubmitted()
    }
  }

  const handleFormSubmit = () => {
    handleSubmit(onSave)()
  }

  useAutoSave({
    form,
    onSave,
    delay: 1000,
    enabled: !inKYCMode,
  })

  return (
    <Form {...form}>
      <form
        onSubmit={(e) => {
          e.preventDefault()
        }}
        className="max-w-2xl"
      >
        <SettingsGroup>
          {!inKYCMode && (
            <>
              <SettingsGroupItem
                title="Identifier"
                description="Unique identifier for your workspace"
              >
                <FormControl>
                  <CopyToClipboardInput
                    value={workspace.id}
                    onCopy={() => {
                      toast({
                        title: 'Copied To Clipboard',
                        description: `Workspace ID was copied to clipboard`,
                      })
                    }}
                  />
                </FormControl>
              </SettingsGroupItem>
              <SettingsGroupItem
                title="Workspace Slug"
                description="Used for your public file sharing page, links, etc."
              >
                <FormControl>
                  <CopyToClipboardInput
                    value={workspace.slug}
                    onCopy={() => {
                      toast({
                        title: 'Copied To Clipboard',
                        description: `Workspace Slug was copied to clipboard`,
                      })
                    }}
                  />
                </FormControl>
              </SettingsGroupItem>
            </>
          )}
          <div className="flex flex-col gap-y-4 p-4">
            <WorkspaceDetailsForm workspace={workspace} inKYCMode={inKYCMode} />
          </div>

          {inKYCMode && (
            <SettingsGroupActions>
              <ConfirmationButton
                onConfirm={handleFormSubmit}
                warningMessage="This information cannot be changed once submitted. Are you sure?"
                buttonText="Submit for Review"
                size="default"
                confirmText="Submit"
                disabled={!formState.isDirty}
                loading={updateWorkspace.isPending}
                requireConfirmation={true}
              />
            </SettingsGroupActions>
          )}
        </SettingsGroup>
      </form>
    </Form>
  )
}

export default WorkspaceProfileSettings

import { CONFIG } from '@/utils/config'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@rapidly-tech/ui/components/forms/Select'
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { type MouseEvent } from 'react'

import ImageUpload from '@/components/Form/ImageUpload'
import { Icon } from '@iconify/react'
import { enums } from '@rapidly-tech/client'
import { Checkbox } from '@rapidly-tech/ui/components/primitives/checkbox'
import Link from 'next/link'
import { useCallback, useMemo } from 'react'
import { useFieldArray, useFormContext } from 'react-hook-form'
import { EnhancedOAuth2ClientConfiguration } from './NewOAuthClientModal'

// ---------------------------------------------------------------------------
// Reusable form-field components for the OAuth2 client configuration panels.
// Each field is a controlled component driven by react-hook-form context.
// ---------------------------------------------------------------------------

/** OAuth application display name. */
export const FieldName = () => {
  const { control } = useFormContext<EnhancedOAuth2ClientConfiguration>()

  return (
    <FormField
      control={control}
      name="client_name"
      rules={{ required: 'Application name is required' }}
      render={({ field }) => (
        <FormItem className="flex flex-col gap-4">
          <FormLabel>Application Name</FormLabel>
          <FormControl>
            <Input {...field} placeholder="My OAuth Application" />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )
}

/** Confidential vs public client selector with documentation link. */
export const FieldClientType = () => {
  const { control } = useFormContext<EnhancedOAuth2ClientConfiguration>()

  const docsHref = `${CONFIG.DOCS_BASE_URL}/documentation/integration-guides/authenticating-with-rapidly`

  return (
    <FormField
      control={control}
      name="token_endpoint_auth_method"
      rules={{ required: 'Please choose a client type' }}
      render={({ field }) => (
        <FormItem>
          <FormLabel>Client Type</FormLabel>
          <Select onValueChange={field.onChange} defaultValue={field.value}>
            <FormControl>
              <SelectTrigger>
                <SelectValue placeholder="Select a client type" />
              </SelectTrigger>
            </FormControl>
            <SelectContent>
              <SelectItem value="client_secret_post">
                Confidential Client
              </SelectItem>
              <SelectItem value="none">Public Client</SelectItem>
            </SelectContent>
          </Select>
          <FormMessage />
          <FormDescription>
            For public clients (SPA or mobile), choose <em>Public Client</em>.
            Server-side apps should use <em>Confidential Client</em>.{' '}
            <Link
              className="text-slate-600 hover:text-slate-500 dark:text-slate-400 dark:hover:text-slate-300"
              href={docsHref}
              target="_blank"
              rel="noopener noreferrer"
            >
              Learn more
            </Link>
            .
          </FormDescription>
        </FormItem>
      )}
    />
  )
}

/** Read-only display of the generated client identifier. */
export const FieldClientID = ({ clientId }: { clientId: string }) => (
  <FormItem className="flex flex-col gap-4">
    <FormLabel>Client ID</FormLabel>
    <FormControl>
      <Input value={clientId} placeholder="Client ID" readOnly />
    </FormControl>
    <FormMessage />
  </FormItem>
)

/** Read-only display of the client secret with a security warning. */
export const FieldClientSecret = ({
  clientSecret,
}: {
  clientSecret: string
}) => {
  const docsHref = `${CONFIG.DOCS_BASE_URL}/documentation/integration-guides/authenticating-with-rapidly`

  return (
    <FormItem className="flex flex-col gap-4">
      <FormLabel>Client Secret</FormLabel>
      <FormControl>
        <Input value={clientSecret} placeholder="Client Secret" readOnly />
      </FormControl>
      <FormMessage />
      <FormDescription>
        Keep this value secure &mdash; never embed it in public-facing code.{' '}
        <Link
          className="text-slate-600 hover:text-slate-500 dark:text-slate-400 dark:hover:text-slate-300"
          href={docsHref}
          target="_blank"
          rel="noopener noreferrer"
        >
          Security guidance
        </Link>
        .
      </FormDescription>
    </FormItem>
  )
}

/** Square logo upload with 1:1 ratio validation. */
export const FieldLogo = () => {
  const { control } = useFormContext<EnhancedOAuth2ClientConfiguration>()

  return (
    <FormField
      control={control}
      name="logo_uri"
      render={({ field }) => (
        <FormItem className="flex flex-col gap-4">
          <FormLabel>Logotype</FormLabel>
          <FormControl>
            <ImageUpload
              height={200}
              width={200}
              onUploaded={field.onChange}
              defaultValue={field.value || undefined}
              validate={(img) =>
                img.width !== img.height
                  ? 'Logo must be square (1:1 aspect ratio)'
                  : undefined
              }
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )
}

/** Dynamic list of OAuth redirect URIs with add/remove controls. */
export const FieldRedirectURIs = () => {
  const { control, setValue } =
    useFormContext<EnhancedOAuth2ClientConfiguration>()

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'redirect_uris',
    rules: { minLength: 1 },
  })

  const addRedirectUri = useCallback(
    (e: MouseEvent<HTMLButtonElement>) => {
      e.preventDefault()
      append({ uri: 'https://' })
    },
    [append],
  )

  return (
    <div className="flex flex-col gap-y-4">
      <div className="flex flex-row items-center justify-between gap-x-4">
        <FormLabel>Redirect URIs</FormLabel>
        <Button
          className="aspect-square w-8"
          size="icon"
          variant="secondary"
          onClick={addRedirectUri}
        >
          <Icon icon="solar:add-circle-linear" className="text-[1em]" />
        </Button>
      </div>
      <div className="flex flex-col gap-y-2">
        {fields.map(({ id }, index) => (
          <FormField
            key={id}
            control={control}
            name={`redirect_uris.${index}.uri`}
            rules={{ required: 'Redirect URI is required' }}
            render={({ field }) => (
              <FormItem>
                <FormControl>
                  <div className="flex flex-row items-center gap-2">
                    <Input
                      name={field.name}
                      value={field.value}
                      placeholder="https://"
                      onChange={(e) => {
                        field.onChange(e.target.value)
                        setValue(`redirect_uris.${index}.uri`, e.target.value)
                      }}
                    />
                    {index > 0 && (
                      <Button
                        className="border-none bg-transparent text-base opacity-50 transition-opacity hover:opacity-100 dark:bg-transparent"
                        size="icon"
                        variant="secondary"
                        type="button"
                        onClick={() => remove(index)}
                      >
                        <Icon
                          icon="solar:close-circle-linear"
                          className="text-[1em]"
                        />
                      </Button>
                    )}
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        ))}
      </div>
    </div>
  )
}

/** Checkbox grid of available OAuth scopes with select-all toggle. */
export const FieldScopes = () => {
  const { control, watch, setValue } =
    useFormContext<EnhancedOAuth2ClientConfiguration>()

  const sortedAvailableScopes = useMemo(
    () =>
      Array.from(enums.availableScopeValues).sort((a, b) => a.localeCompare(b)),
    [],
  )

  const currentScopes = watch('scope')

  const allSelected = useMemo(
    () => sortedAvailableScopes.every((s) => currentScopes.includes(s)),
    [currentScopes, sortedAvailableScopes],
  )

  const toggleAll = useCallback(
    (e: MouseEvent<HTMLButtonElement>) => {
      e.preventDefault()
      setValue('scope', allSelected ? [] : sortedAvailableScopes)
    },
    [setValue, allSelected, sortedAvailableScopes],
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-row items-center justify-between">
        <h2 className="text-sm leading-none font-medium">Scopes</h2>
        <Button onClick={toggleAll} variant="secondary" size="sm">
          {allSelected ? 'Unselect All' : 'Select All'}
        </Button>
      </div>

      <div className="flex flex-col gap-2">
        {sortedAvailableScopes.map((scope) => (
          <FormField
            key={scope}
            control={control}
            name="scope"
            render={({ field }) => (
              <FormItem className="flex flex-row items-center space-y-0 space-x-3">
                <FormControl>
                  <Checkbox
                    checked={field.value?.includes(scope)}
                    onCheckedChange={(checked) => {
                      field.onChange(
                        checked
                          ? [...(field.value || []), scope]
                          : (field.value || []).filter((v) => v !== scope),
                      )
                    }}
                  />
                </FormControl>
                <FormLabel className="text-sm leading-none">{scope}</FormLabel>
                <FormMessage />
              </FormItem>
            )}
          />
        ))}
      </div>
    </div>
  )
}

/** Homepage URL for the OAuth application. */
export const FieldClientURI = () => {
  const { control } = useFormContext<EnhancedOAuth2ClientConfiguration>()

  return (
    <FormField
      control={control}
      name="client_uri"
      rules={{ required: 'A homepage URL is required' }}
      render={({ field }) => (
        <FormItem className="flex flex-col gap-4">
          <FormLabel>Homepage URL</FormLabel>
          <FormControl>
            <Input
              {...field}
              value={field.value || ''}
              placeholder="https://"
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )
}

/** Optional link to Terms of Service document. */
export const FieldTOS = () => {
  const { control } = useFormContext<EnhancedOAuth2ClientConfiguration>()

  return (
    <FormField
      control={control}
      name="tos_uri"
      render={({ field }) => (
        <FormItem className="flex flex-col gap-4">
          <FormLabel>Terms of Service</FormLabel>
          <FormControl>
            <Input
              {...field}
              value={field.value || ''}
              placeholder="Link to Terms of Service"
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )
}

/** Optional link to Privacy Policy document. */
export const FieldPrivacy = () => {
  const { control } = useFormContext<EnhancedOAuth2ClientConfiguration>()

  return (
    <FormField
      control={control}
      name="policy_uri"
      render={({ field }) => (
        <FormItem className="flex flex-col gap-4">
          <FormLabel>Privacy Policy</FormLabel>
          <FormControl>
            <Input
              {...field}
              value={field.value || ''}
              placeholder="Link to Privacy Policy"
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )
}

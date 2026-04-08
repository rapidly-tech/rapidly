import { CONFIG } from '@/utils/config'
import { enums, schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@rapidly-tech/ui/components/forms/Select'
import { Checkbox } from '@rapidly-tech/ui/components/primitives/checkbox'
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import Link from 'next/link'
import { useCallback, useEffect, useMemo, type MouseEvent } from 'react'
import { useFormContext } from 'react-hook-form'

// ---------------------------------------------------------------------------
// Shared type for create / update payloads
// ---------------------------------------------------------------------------

type EndpointFormValues =
  | schemas['WebhookEndpointCreate']
  | schemas['WebhookEndpointUpdate']

// ---------------------------------------------------------------------------
// Field: Endpoint URL (must be HTTPS)
// ---------------------------------------------------------------------------

export const FieldUrl = () => {
  const { control } = useFormContext<EndpointFormValues>()

  return (
    <FormField
      control={control}
      name="url"
      rules={{
        required: 'URL is required',
        validate: (value) =>
          !value || !value.startsWith('https://')
            ? 'URL must start with https://'
            : true,
      }}
      render={({ field }) => (
        <FormItem className="flex flex-col gap-1">
          <FormLabel>URL</FormLabel>
          <FormControl>
            <Input
              {...field}
              value={field.value || ''}
              placeholder="https://..."
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )
}

// ---------------------------------------------------------------------------
// Field: Payload format — auto-detects Discord & Slack URLs
// ---------------------------------------------------------------------------

export const FieldFormat = () => {
  const { control, watch, setValue } = useFormContext<EndpointFormValues>()

  const url = watch('url')

  useEffect(() => {
    if (!url) return
    if (url.startsWith('https://discord.com/api/webhooks')) {
      setValue('format', 'discord')
    } else if (url.startsWith('https://hooks.slack.com/services/')) {
      setValue('format', 'slack')
    }
  }, [url, setValue])

  return (
    <FormField
      control={control}
      name="format"
      rules={{ required: 'Payload format is required' }}
      render={({ field }) => (
        <FormItem className="flex flex-col gap-1">
          <FormLabel>Format</FormLabel>
          <FormControl>
            <Select
              {...field}
              value={field.value || undefined}
              onValueChange={field.onChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a payload format" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="raw">Raw</SelectItem>
                <SelectItem value="discord">Discord</SelectItem>
                <SelectItem value="slack">Slack</SelectItem>
              </SelectContent>
            </Select>
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )
}

// ---------------------------------------------------------------------------
// Field: Subscribed event types with select-all toggle
// ---------------------------------------------------------------------------

export const FieldEvents = () => {
  const { control, setValue, watch } = useFormContext<EndpointFormValues>()

  const allEvents = useMemo(
    () => Object.values(enums.webhookEventTypeValues),
    [],
  )

  const currentEvents = watch('events')

  const allSelected = useMemo(
    () => allEvents.every((evt) => currentEvents?.includes(evt)),
    [currentEvents, allEvents],
  )

  const toggleAll = useCallback(
    (e: MouseEvent<HTMLButtonElement>) => {
      e.preventDefault()
      setValue('events', allSelected ? [] : allEvents)
    },
    [setValue, allSelected, allEvents],
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-row items-center justify-between">
        <h2 className="text-sm leading-none font-medium">Events</h2>
        <Button onClick={toggleAll} variant="secondary" size="sm">
          {allSelected ? 'Unselect All' : 'Select All'}
        </Button>
      </div>

      <div className="flex flex-col gap-y-2">
        {allEvents.map((event) => (
          <FormField
            key={event}
            control={control}
            name="events"
            render={({ field }) => {
              const schemaHref = `${CONFIG.DOCS_BASE_URL}/api-reference/webhooks/${event}`

              return (
                <FormItem className="flex flex-row items-center space-y-0 space-x-3">
                  <FormControl>
                    <Checkbox
                      checked={field.value?.includes(event) ?? false}
                      onCheckedChange={(checked: boolean) => {
                        field.onChange(
                          checked
                            ? [...(field.value || []), event]
                            : (field.value || []).filter(
                                (v: string) => v !== event,
                              ),
                        )
                      }}
                    />
                  </FormControl>
                  <FormLabel className="text-sm leading-none">
                    {event}
                  </FormLabel>
                  <Link
                    className="text-xs text-slate-600 dark:text-slate-400"
                    href={schemaHref}
                    target="_blank"
                  >
                    Schema
                  </Link>
                  <FormMessage />
                </FormItem>
              )
            }}
          />
        ))}
      </div>
    </div>
  )
}

'use client'

import DateRangePicker, {
  DateRange,
} from '@/components/Metrics/DateRangePicker'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@rapidly-tech/ui/components/forms/Select'
import React, { useCallback } from 'react'
import { WebhookEventTypeSelect } from './WebhookEventTypeSelect'

interface WebhookFilterProps {
  onDateRangeChange: (dateRange?: DateRange) => void
  dateRange?: DateRange
  className?: string
  succeeded?: string
  onSucceededChange: (value: string | null) => void
  httpCodeClass?: string
  onHttpCodeClassChange: (value: string | null) => void
  eventTypes: string[]
  onEventTypesChange: (eventTypes: string[]) => void
  query?: string
  onQueryChange: (value: string) => void
}

const ALL_SENTINEL = 'all'

const normalizeFilterValue = (value: string): string | null =>
  value === ALL_SENTINEL ? null : value

const StatusFilter = ({
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger className="w-auto min-w-32">
      <SelectValue placeholder="Status" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All Statuses</SelectItem>
      <SelectItem value="true">Succeeded</SelectItem>
      <SelectItem value="false">Failed</SelectItem>
    </SelectContent>
  </Select>
)

const HttpCodeFilter = ({
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger className="w-auto min-w-32">
      <SelectValue placeholder="HTTP Status" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All HTTP Responses</SelectItem>
      <SelectItem value="2xx">2xx Success</SelectItem>
      <SelectItem value="3xx">3xx Redirect</SelectItem>
      <SelectItem value="4xx">4xx Client Error</SelectItem>
      <SelectItem value="5xx">5xx Server Error</SelectItem>
    </SelectContent>
  </Select>
)

export const WebhookFilter: React.FC<WebhookFilterProps> = ({
  onDateRangeChange,
  dateRange,
  className,
  succeeded,
  onSucceededChange,
  httpCodeClass,
  onHttpCodeClassChange,
  eventTypes,
  onEventTypesChange,
  query,
  onQueryChange,
}) => {
  const handleSucceededChange = useCallback(
    (value: string) => onSucceededChange(normalizeFilterValue(value)),
    [onSucceededChange],
  )

  const handleHttpCodeChange = useCallback(
    (value: string) => onHttpCodeClassChange(normalizeFilterValue(value)),
    [onHttpCodeClassChange],
  )

  const handleQueryInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => onQueryChange(e.target.value),
    [onQueryChange],
  )

  return (
    <div className={`flex flex-wrap items-center gap-4 ${className ?? ''}`}>
      <StatusFilter
        value={succeeded ?? ALL_SENTINEL}
        onChange={handleSucceededChange}
      />

      <HttpCodeFilter
        value={httpCodeClass ?? ALL_SENTINEL}
        onChange={handleHttpCodeChange}
      />

      <WebhookEventTypeSelect
        selectedEventTypes={eventTypes}
        onSelectEventTypes={onEventTypesChange}
      />

      <Input
        placeholder="Search Deliveries"
        value={query ?? ''}
        onChange={handleQueryInput}
        className="w-auto min-w-48"
      />

      <DateRangePicker date={dateRange} onDateChange={onDateRangeChange} />
    </div>
  )
}

export default WebhookFilter

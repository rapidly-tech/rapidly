'use client'

import { enums, schemas } from '@rapidly-tech/client'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@rapidly-tech/ui/components/forms/Select'
import { useCallback, useMemo } from 'react'

interface CurrencySelectorProps {
  value: schemas['PresentmentCurrency']
  onChange: (value: string) => void
  disabled?: boolean
}

const PLACEHOLDER_TEXT = 'Select currency'

const formatCurrencyLabel = (code: string): string => code.toUpperCase()

const CurrencyOption = ({ code }: { code: string }) => (
  <SelectItem key={code} value={code}>
    {formatCurrencyLabel(code)}
  </SelectItem>
)

export const CurrencySelector = ({
  value,
  onChange,
  disabled = false,
}: CurrencySelectorProps) => {
  const handleChange = useCallback(
    (selected: string) => onChange(selected),
    [onChange],
  )

  const currencyOptions = useMemo(
    () =>
      enums.presentmentCurrencyValues.map((code) => (
        <CurrencyOption key={code} code={code} />
      )),
    [],
  )

  return (
    <Select value={value} onValueChange={handleChange} disabled={disabled}>
      <SelectTrigger>
        <SelectValue placeholder={PLACEHOLDER_TEXT} />
      </SelectTrigger>
      <SelectContent>{currencyOptions}</SelectContent>
    </Select>
  )
}

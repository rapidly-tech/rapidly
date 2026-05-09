import { DEBOUNCE_DELAY_MS } from '@/utils/constants/timings'
import { useEffect, useState } from 'react'
import { FieldValues, UseFormReturn, useWatch } from 'react-hook-form'
import { useDebouncedCallback } from './utils'

interface AutoSaveConfig<T extends FieldValues> {
  form: UseFormReturn<T>
  onSave: (data: T) => Promise<void>
  delay?: number
  enabled?: boolean
}

// Persists form values after a quiet period when the form has unsaved changes
export function useAutoSave<T extends FieldValues>({
  form,
  onSave,
  delay = DEBOUNCE_DELAY_MS,
  enabled = true,
}: AutoSaveConfig<T>) {
  const [isSaving, setIsSaving] = useState(false)

  const watchedValues = useWatch({ control: form.control })
  const { isDirty } = form.formState

  const persist = useDebouncedCallback(
    async () => {
      setIsSaving(true)
      try {
        await onSave(form.getValues())
      } finally {
        setIsSaving(false)
      }
    },
    delay,
    [onSave, form],
  )

  useEffect(() => {
    if (enabled && isDirty && !isSaving) persist()
  }, [watchedValues, enabled, isDirty, persist, isSaving])

  return { isSaving }
}

import { FormField } from '@rapidly-tech/ui/components/primitives/form'

import { Icon } from '@iconify/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  FormControl,
  FormItem,
  FormLabel,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { useCallback } from 'react'
import { useFieldArray, useFormContext } from 'react-hook-form'
import { CustomerUpdateForm } from './EditCustomerModal'

/**
 * Dynamic key-value editor for customer metadata.
 * Supports adding up to 50 entries and removing any individual row.
 */
export const CustomerMetadataForm = () => {
  const { control } = useFormContext<CustomerUpdateForm>()

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'metadata',
    rules: { maxLength: 50 },
  })

  const addRow = useCallback(() => append({ key: '', value: '' }), [append])

  return (
    <FormItem>
      <div className="flex flex-row items-center justify-between gap-2 py-2">
        <FormLabel>Metadata</FormLabel>
        <Button
          className="h-8 w-8 rounded-full"
          size="icon"
          type="button"
          onClick={addRow}
        >
          <Icon icon="solar:add-circle-linear" className="h-5 w-5" />
        </Button>
      </div>
      <div className="flex flex-col gap-2">
        {fields.map((field, index) => (
          <div key={field.id} className="flex flex-row items-center gap-2">
            <FormField
              control={control}
              name={`metadata.${index}.key`}
              render={({ field }) => (
                <>
                  <FormControl>
                    <Input
                      {...field}
                      value={field.value || ''}
                      placeholder="Key"
                    />
                  </FormControl>
                  <FormMessage />
                </>
              )}
            />
            <FormField
              control={control}
              name={`metadata.${index}.value`}
              render={({ field }) => (
                <>
                  <FormControl>
                    <Input
                      {...field}
                      value={field.value.toString() || ''}
                      placeholder="Value"
                    />
                  </FormControl>
                  <FormMessage />
                </>
              )}
            />
            <Button
              className="border-none bg-transparent text-base opacity-50 transition-opacity hover:opacity-100 dark:bg-transparent"
              size="icon"
              variant="secondary"
              type="button"
              onClick={() => remove(index)}
            >
              <Icon icon="solar:close-circle-linear" className="text-[1em]" />
            </Button>
          </div>
        ))}
      </div>
    </FormItem>
  )
}

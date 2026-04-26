import revalidate from '@/app/actions'
import { useUpdateCustomer } from '@/hooks/api'
import { setValidationErrors } from '@/utils/api/errors'
import { isValidationError, schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from '../Toast/use-toast'
import { CustomerMetadataForm } from './CustomerMetadataForm'

export type CustomerUpdateForm = Omit<schemas['CustomerUpdate'], 'metadata'> & {
  metadata: { key: string; value: string | number | boolean }[]
}

/**
 * Slide-over modal for updating a customer record.
 * Edits name, email, external ID, and key-value metadata.
 */
export const EditCustomerModal = ({
  customer,
  onClose,
}: {
  customer: schemas['Customer']
  onClose: () => void
}) => {
  const form = useForm<CustomerUpdateForm>({
    defaultValues: {
      name: customer.name || '',
      email: customer.email || '',
      external_id: customer.external_id || '',
      metadata: Object.entries(customer.metadata).map(([key, value]) => ({
        key,
        value,
      })),
    },
  })

  const updateCustomer = useUpdateCustomer(customer.id, customer.workspace_id)

  const handleSave = useCallback(
    (values: CustomerUpdateForm) => {
      const payload = {
        ...values,
        metadata: values.metadata?.reduce(
          (acc, { key, value }) => ({ ...acc, [key]: value }),
          {},
        ),
      }

      updateCustomer.mutateAsync(payload).then(({ error }) => {
        if (error) {
          if (error.detail) {
            if (isValidationError(error.detail)) {
              setValidationErrors(error.detail, form.setError)
            } else {
              toast({
                title: 'Update Failed',
                description: `Could not update ${customer.email}: ${error.detail}`,
              })
            }
          }
          return
        }

        toast({
          title: 'Customer Updated',
          description: `${customer.email} saved`,
        })
        revalidate(`customer:${customer.id}`)
        onClose()
      })
    },
    [updateCustomer, customer, form, onClose],
  )

  return (
    <div className="flex flex-col gap-8 overflow-y-auto px-8 py-12">
      <h2 className="text-xl">Edit Customer</h2>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(handleSave)}
          className="flex flex-col gap-8"
        >
          <div className="flex flex-col gap-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input {...field} value={field.value || ''} />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="email"
              rules={{
                required: 'Email is required',
                pattern: {
                  value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                  message: 'Please enter a valid email address',
                },
              }}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input {...field} value={field.value || ''} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="external_id"
              disabled={!!customer.external_id}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>External ID</FormLabel>
                  <FormDescription>
                    Maps this customer to a record in your own system. Once set
                    it cannot be changed.
                  </FormDescription>
                  <FormControl>
                    <Input {...field} value={field.value || ''} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="metadata"
              render={() => <CustomerMetadataForm />}
            />
          </div>
          <Button
            type="submit"
            className="self-start"
            loading={updateCustomer.isPending}
          >
            Save Customer
          </Button>
        </form>
      </Form>
    </div>
  )
}

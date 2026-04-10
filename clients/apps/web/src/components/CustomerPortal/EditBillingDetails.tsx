import { setValidationErrors } from '@/utils/api/errors'
import { enums, type schemas } from '@rapidly-tech/client'
import { isValidationError } from '@rapidly-tech/customer-portal/core'
import { useCustomerPortalCustomer } from '@rapidly-tech/customer-portal/react'
import Button from '@rapidly-tech/ui/components/forms/Button'
import CountryPicker from '@rapidly-tech/ui/components/forms/CountryPicker'
import CountryStatePicker from '@rapidly-tech/ui/components/forms/CountryStatePicker'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { useCallback, useEffect, useMemo } from 'react'
import { type Control, type FieldPath, useForm } from 'react-hook-form'

type CustomerUpdate = schemas['CustomerPortalCustomerUpdate']
type AddressInput = schemas['AddressInput']

const INPUT_CLASSES = 'bg-white shadow-xs dark:bg-slate-900 dark:shadow-none'

const REQUIRED_RULE = { required: 'This field is required' } as const

const COUNTRIES_WITH_STATES = new Set(['US', 'CA'])

const needsStatePicker = (country: string | undefined): boolean =>
  Boolean(country && COUNTRIES_WITH_STATES.has(country))

const buildDefaultValues = (
  customer: schemas['CustomerPortalCustomer'] | undefined,
): Partial<CustomerUpdate> => ({
  billing_name: customer?.billing_name || customer?.name,
  billing_address: customer?.billing_address as AddressInput,
})

const buildResetValues = (
  updatedCustomer: schemas['CustomerPortalCustomer'],
): Partial<CustomerUpdate> => ({
  billing_name: updatedCustomer.billing_name || updatedCustomer.name,
  billing_address: updatedCustomer.billing_address as AddressInput | null,
})

const AddressField = ({
  control,
  name,
  placeholder,
  autoComplete,
  rules,
}: {
  control: Control<CustomerUpdate>
  name: FieldPath<CustomerUpdate>
  placeholder: string
  autoComplete: string
  rules?: Record<string, string>
}) => (
  <FormControl>
    <FormField
      control={control}
      name={name}
      rules={rules}
      render={({ field }) => (
        <div className="flex flex-col gap-y-2">
          <Input
            type="text"
            autoComplete={autoComplete}
            placeholder={placeholder}
            className={INPUT_CLASSES}
            {...field}
            value={String(field.value ?? '')}
          />
          <FormMessage />
        </div>
      )}
    />
  </FormControl>
)

const EditBillingDetails = ({ onSuccess }: { onSuccess: () => void }) => {
  const { data: customer, update } = useCustomerPortalCustomer()

  const defaults = useMemo(() => buildDefaultValues(customer), [customer])

  const form = useForm<CustomerUpdate>({ defaultValues: defaults })

  const {
    control,
    handleSubmit,
    watch,
    setError,
    setValue,
    reset,
    formState: { errors, isDirty },
  } = form

  const country = watch('billing_address.country')
  const showStatePicker = needsStatePicker(country)

  useEffect(() => {
    if (!showStatePicker) {
      setValue('billing_address.state', null)
    }
  }, [showStatePicker, setValue])

  const onSubmit = useCallback(
    async (data: CustomerUpdate) => {
      try {
        const updatedCustomer = await update.mutateAsync(data)
        reset(buildResetValues(updatedCustomer))
        onSuccess()
      } catch (e) {
        if (isValidationError(e)) {
          setValidationErrors(e.errors, setError)
        } else {
          throw e
        }
      }
    },
    [update, onSuccess, setError, reset],
  )

  if (!customer) return null

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-y-6">
        <FormItem>
          <FormLabel>Email</FormLabel>
          <FormControl>
            <Input
              type="email"
              value={customer.email}
              disabled
              readOnly
              className={INPUT_CLASSES}
            />
          </FormControl>
        </FormItem>

        <FormField
          control={control}
          name="billing_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Billing Name</FormLabel>
              <FormControl>
                <Input
                  type="text"
                  autoComplete="workspace"
                  placeholder="Company or legal name for payments (optional)"
                  {...field}
                  value={field.value || ''}
                  className={INPUT_CLASSES}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormItem className="flex flex-col gap-y-3">
          <FormLabel>Billing address</FormLabel>

          <AddressField
            control={control}
            name="billing_address.line1"
            placeholder="Line 1"
            autoComplete="billing address-line1"
            rules={REQUIRED_RULE}
          />

          <AddressField
            control={control}
            name="billing_address.line2"
            placeholder="Line 2"
            autoComplete="billing address-line2"
          />

          <div className="grid grid-cols-2 gap-x-3">
            <AddressField
              control={control}
              name="billing_address.postal_code"
              placeholder="Postal code"
              autoComplete="billing postal-code"
              rules={REQUIRED_RULE}
            />
            <AddressField
              control={control}
              name="billing_address.city"
              placeholder="City"
              autoComplete="billing address-level2"
              rules={REQUIRED_RULE}
            />
          </div>

          <FormControl>
            <FormField
              control={control}
              name="billing_address.country"
              rules={REQUIRED_RULE}
              render={({ field }) => (
                <div className="flex flex-col gap-y-2">
                  <CountryPicker
                    autoComplete="billing country"
                    value={field.value || undefined}
                    onChange={field.onChange}
                    allowedCountries={enums.addressInputCountryValues}
                  />
                  <FormMessage />
                </div>
              )}
            />
          </FormControl>

          {showStatePicker && (
            <FormControl>
              <FormField
                control={control}
                name="billing_address.state"
                rules={REQUIRED_RULE}
                render={({ field }) => (
                  <div className="flex flex-col gap-y-2">
                    <CountryStatePicker
                      autoComplete="billing address-level1"
                      country={country}
                      value={field.value || undefined}
                      onChange={field.onChange}
                    />
                    <FormMessage />
                  </div>
                )}
              />
            </FormControl>
          )}

          {errors.billing_address?.message && (
            <p className="text-destructive-foreground text-sm">
              {errors.billing_address.message}
            </p>
          )}
        </FormItem>

        <Button
          type="submit"
          loading={update.isPending}
          disabled={update.isPending || !isDirty}
          className="self-start"
        >
          Update Billing Details
        </Button>
      </form>
    </Form>
  )
}

export default EditBillingDetails

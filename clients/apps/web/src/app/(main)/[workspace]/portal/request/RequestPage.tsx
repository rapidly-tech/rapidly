'use client'

// ── Imports ──

import { useCustomerPortalSessionRequest } from '@/hooks/api'
import { setValidationErrors } from '@/utils/api/errors'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import ElevatedCard from '@rapidly-tech/ui/components/layout/ElevatedCard'
import { useRouter } from 'next/navigation'

import { api } from '@/utils/client'
import { schemas } from '@rapidly-tech/client'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { Label } from '@rapidly-tech/ui/components/primitives/label'
import {
  RadioGroup,
  RadioGroupItem,
} from '@rapidly-tech/ui/components/primitives/radio-group'
import { useCallback, useState } from 'react'
import { useForm } from 'react-hook-form'

// ── Types ──

interface CustomerSelectionOption {
  id: string
  name: string | null
}

interface CustomerSelectionRequiredResponse {
  error: string
  detail: string
  customers: CustomerSelectionOption[]
}

function isCustomerSelectionRequired(
  value: unknown,
): value is CustomerSelectionRequiredResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    'customers' in value &&
    Array.isArray((value as CustomerSelectionRequiredResponse).customers)
  )
}
// ── Main Component ──

const ClientPage = ({
  workspace,
  email,
}: {
  workspace: schemas['CustomerWorkspace']
  email?: string
}) => {
  const router = useRouter()
  const form = useForm<{ email: string }>({
    defaultValues: {
      email: email || '',
    },
  })
  const { control, handleSubmit, setError, getValues } = form
  const sessionRequest = useCustomerPortalSessionRequest(api, workspace.id)

  const [customers, setCustomers] = useState<CustomerSelectionOption[]>([])
  const [showCustomerPicker, setShowCustomerPicker] = useState(false)
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>('')

  const onSubmit = useCallback(
    async ({ email }: { email: string }, customerId?: string) => {
      const response = await sessionRequest.mutateAsync({
        email,
        customer_id: customerId,
      })

      // Handle 409 - customer selection required
      if (
        response.response.status === 409 &&
        isCustomerSelectionRequired(response.error)
      ) {
        if (response.error.customers.length > 0) {
          setCustomers(response.error.customers)
          setShowCustomerPicker(true)
          return
        }
      }

      if (response.error) {
        if (response.error.detail && Array.isArray(response.error.detail)) {
          setValidationErrors(response.error.detail, setError)
        }
        return
      }
      router.push(`/${workspace.slug}/portal/authenticate`)
    },
    [sessionRequest, setError, router, workspace],
  )

  const handleCustomerSelect = useCallback(async () => {
    if (!selectedCustomerId) return
    const email = getValues('email')
    await onSubmit({ email }, selectedCustomerId)
  }, [selectedCustomerId, getValues, onSubmit])

  if (showCustomerPicker) {
    return (
      <ElevatedCard className="flex w-full max-w-7xl flex-col items-center gap-12 md:px-32 md:py-24">
        <div className="flex w-full flex-col gap-y-6 md:max-w-sm">
          <div className="flex flex-col gap-4">
            <h2 className="rp-text-primary text-2xl">Select an account</h2>
            <p className="text-slate-500 dark:text-slate-400">
              Multiple accounts are associated with this email. Please select
              the account you want to access.
            </p>
          </div>
          <RadioGroup
            value={selectedCustomerId}
            onValueChange={setSelectedCustomerId}
            className="flex flex-col gap-3"
          >
            {customers.map((customer) => (
              <div
                key={customer.id}
                className="flex items-center space-x-3 rounded-lg border p-4 hover:bg-slate-50 dark:hover:bg-slate-900"
              >
                <RadioGroupItem value={customer.id} id={customer.id} />
                <Label
                  htmlFor={customer.id}
                  className="flex-1 cursor-pointer font-medium"
                >
                  {customer.name || 'Unnamed account'}
                </Label>
              </div>
            ))}
          </RadioGroup>
          <div className="flex gap-3">
            <Button
              variant="ghost"
              size="lg"
              onClick={() => {
                setShowCustomerPicker(false)
                setSelectedCustomerId('')
                setCustomers([])
              }}
            >
              Back
            </Button>
            <Button
              size="lg"
              className="flex-1"
              loading={sessionRequest.isPending}
              disabled={sessionRequest.isPending || !selectedCustomerId}
              onClick={handleCustomerSelect}
            >
              Continue
            </Button>
          </div>
        </div>
      </ElevatedCard>
    )
  }

  return (
    <ElevatedCard className="flex w-full max-w-7xl flex-col items-center gap-12 md:px-32 md:py-24">
      <div className="flex w-full flex-col gap-y-6 md:max-w-sm">
        <div className="flex flex-col gap-4">
          <h2 className="rp-text-primary text-2xl">Sign in</h2>
          <p className="text-slate-500 dark:text-slate-400">
            Enter your email address to access your purchases. A verification
            code will be sent to you.
          </p>
        </div>
        <Form {...form}>
          <form
            className="flex w-full flex-col gap-y-6"
            onSubmit={handleSubmit((data) => onSubmit(data))}
          >
            <FormField
              control={control}
              name="email"
              rules={{
                required: 'This field is required',
              }}
              render={({ field }) => {
                return (
                  <FormItem>
                    <FormControl>
                      <Input
                        type="email"
                        required
                        placeholder="Email address"
                        autoComplete="email"
                        className="dark:bg-rapidly-800 bg-white shadow-xs"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )
              }}
            />
            <Button
              type="submit"
              size="lg"
              loading={sessionRequest.isPending}
              disabled={sessionRequest.isPending}
            >
              Access my files
            </Button>
          </form>
        </Form>
      </div>
    </ElevatedCard>
  )
}

// ── Exports ──

export default ClientPage

import { CurrencySelector } from '@/components/CurrencySelector'
import { useUpdateWorkspace } from '@/hooks/api'
import { setValidationErrors } from '@/utils/api/errors'
import { api } from '@/utils/client'
import { ALLOWED_STRIPE_ORIGINS, isSafeRedirect } from '@/utils/safe-redirect'
import { enums, isValidationError, schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import CountryPicker from '@rapidly-tech/ui/components/forms/CountryPicker'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { useCallback, useState } from 'react'
import { useForm, useFormContext } from 'react-hook-form'

type WorkspaceAccountForm = schemas['AccountCreateForWorkspace'] & {
  default_presentment_currency: schemas['PresentmentCurrency']
}

const ONBOARDING_ENDPOINT = '/api/accounts/{id}/onboarding_link' as const
const ACCOUNTS_ENDPOINT = '/api/accounts' as const

const navigateToOnboardingLink = (url: string): void => {
  if (isSafeRedirect(url, ALLOWED_STRIPE_ORIGINS)) {
    window.location.href = url
  }
}

const AccountCreateModal = ({
  forWorkspaceId,
  returnPath,
  forceNew = false,
}: {
  forWorkspaceId: string
  returnPath: string
  forceNew?: boolean
}) => {
  const form = useForm<WorkspaceAccountForm>({
    defaultValues: { country: 'US', default_presentment_currency: 'usd' },
  })
  const updateWorkspace = useUpdateWorkspace()
  const { handleSubmit, setError, formState } = form
  const rootError = formState.errors.root

  const [loading, setLoading] = useState(false)

  const goToOnboarding = useCallback(
    async (account: schemas['Account']) => {
      setLoading(true)
      const { data, error } = await api.POST(ONBOARDING_ENDPOINT, {
        params: {
          path: { id: account.id },
          query: { return_path: returnPath },
        },
      })
      setLoading(false)

      if (error) {
        window.location.reload()
        return
      }

      navigateToOnboardingLink(data.url)
    },
    [returnPath],
  )

  const onSubmit = useCallback(
    async (formData: WorkspaceAccountForm) => {
      setLoading(true)

      // Update workspace default currency (best-effort, don't block account creation)
      try {
        await updateWorkspace.mutateAsync({
          id: forWorkspaceId,
          body: {
            default_presentment_currency: formData.default_presentment_currency,
          },
        })
      } catch {
        // Currency update failed — continue with account creation
      }

      const endpoint = forceNew
        ? (`${ACCOUNTS_ENDPOINT}?force_new=true` as typeof ACCOUNTS_ENDPOINT)
        : ACCOUNTS_ENDPOINT
      const { data: account, error } = await api.POST(endpoint, {
        body: {
          account_type: 'stripe',
          country: formData.country,
          workspace_id: forWorkspaceId,
        },
      })

      if (error) {
        if (isValidationError(error.detail)) {
          setValidationErrors(error.detail, setError)
        } else {
          setError('root', { message: error.detail })
        }
        setLoading(false)
        return
      }

      setLoading(false)
      await goToOnboarding(account)
    },
    [
      setLoading,
      forWorkspaceId,
      forceNew,
      goToOnboarding,
      setError,
      updateWorkspace,
    ],
  )

  return (
    <div className="flex flex-col gap-y-6 overflow-auto p-8">
      <h2>Setup payout account</h2>

      <Form {...form}>
        <form
          className="flex flex-col gap-y-4"
          onSubmit={handleSubmit(onSubmit)}
        >
          <AccountCurrency />
          <AccountCountry />
          {rootError && (
            <p className="text-destructive-foreground text-sm">
              {rootError.message}
            </p>
          )}
          <Button
            className="self-start"
            type="submit"
            loading={loading}
            disabled={loading}
          >
            Set up account
          </Button>
        </form>
      </Form>
    </div>
  )
}

const COUNTRY_HELP_TEXT =
  'If this is a personal account, please select your country of residence. If this is a workspace or business, select the country of incorporation.'

export const AccountCountry = () => {
  const { control } = useFormContext<WorkspaceAccountForm>()

  return (
    <FormField
      control={control}
      name="country"
      render={({ field }) => (
        <FormItem>
          <FormLabel>Country</FormLabel>
          <FormControl>
            <CountryPicker
              value={field.value || undefined}
              onChange={field.onChange}
              allowedCountries={enums.stripeAccountCountryValues}
            />
          </FormControl>
          <FormMessage />
          <FormDescription>{COUNTRY_HELP_TEXT}</FormDescription>
        </FormItem>
      )}
    />
  )
}

const AccountCurrency = () => {
  const { control } = useFormContext<WorkspaceAccountForm>()

  return (
    <FormField
      control={control}
      name="default_presentment_currency"
      render={({ field }) => (
        <FormItem>
          <FormLabel>Default Payment Currency</FormLabel>
          <FormControl>
            <CurrencySelector value={field.value} onChange={field.onChange} />
          </FormControl>
          <FormMessage />
          <FormDescription>
            The default currency for your products
          </FormDescription>
        </FormItem>
      )}
    />
  )
}

export default AccountCreateModal

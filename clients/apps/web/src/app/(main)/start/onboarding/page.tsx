'use client'

import revalidate from '@/app/actions'
import { FadeUp } from '@/components/Animated/FadeUp'
import LogoIcon from '@/components/Brand/LogoIcon'
import { CurrencySelector } from '@/components/CurrencySelector'
import SupportedUseCases from '@/components/Onboarding/components/SupportedUseCases'
import { useAuth } from '@/hooks'
import { useCreateWorkspace } from '@/hooks/api'
import { setValidationErrors } from '@/utils/api/errors'
import { api } from '@/utils/client'
import { CONFIG } from '@/utils/config'
import { setConsentCookie } from '@/utils/cookie-consent'
import { ALLOWED_STRIPE_ORIGINS, isSafeRedirect } from '@/utils/safe-redirect'
import { enums, isValidationError, schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import CountryPicker from '@rapidly-tech/ui/components/forms/CountryPicker'
import Input from '@rapidly-tech/ui/components/forms/Input'
import { Checkbox } from '@rapidly-tech/ui/components/primitives/checkbox'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import slugify from 'slugify'

// ── Types ──

type Step = 'workspace' | 'stripe'

type OrgFormSchema = Pick<
  schemas['WorkspaceCreate'],
  'name' | 'slug' | 'default_presentment_currency'
> & {
  terms: boolean
  cookie_consent: boolean
}

// ── Main Component ──

/** Onboarding wizard for new users -- workspace creation and Stripe connect. */
export default function OnboardingPage() {
  const router = useRouter()
  const { currentUser, setWorkspaceMemberships } = useAuth()
  const createWorkspace = useCreateWorkspace()
  const [editedSlug, setEditedSlug] = useState(false)
  const [step, setStep] = useState<Step>('workspace')
  const [createdOrg, setCreatedOrg] = useState<schemas['Workspace'] | null>(
    null,
  )

  // ── Workspace Form Setup ──

  const orgForm = useForm<OrgFormSchema>({
    defaultValues: {
      name: '',
      slug: '',
      default_presentment_currency: 'usd',
      terms: false,
      cookie_consent: false,
    },
  })

  const {
    control: orgControl,
    handleSubmit: handleOrgSubmit,
    watch: watchOrg,
    setError: setOrgError,
    setValue: setOrgValue,
    formState: { errors: orgErrors },
  } = orgForm

  const name = watchOrg('name')
  const slug = watchOrg('slug')
  const terms = watchOrg('terms')

  useEffect(() => {
    if (!editedSlug && name) {
      setOrgValue('slug', slugify(name, { lower: true, strict: true }))
    } else if (slug) {
      setOrgValue(
        'slug',
        slugify(slug, { lower: true, trim: false, strict: true }),
      )
    }
  }, [name, editedSlug, slug, setOrgValue])

  const onOrgSubmit = async (data: OrgFormSchema) => {
    if (!data.terms) return

    // Persist cookie consent choice so the middleware respects it
    setConsentCookie(data.cookie_consent ? 'accepted' : 'declined')

    const { data: workspace, error } = await createWorkspace.mutateAsync({
      name: data.name,
      slug: data.slug,
      default_presentment_currency: data.default_presentment_currency,
    })

    if (error) {
      if (error.detail) {
        setValidationErrors(error.detail, setOrgError)
      }
      return
    }

    await revalidate(`workspaces:${workspace.slug}`, { expire: 0 })
    await revalidate(`users:${currentUser?.id}:workspaces`, {
      expire: 0,
    })
    setWorkspaceMemberships((orgs) => [...orgs, workspace])
    setCreatedOrg(workspace)
    setStep('stripe')
  }

  // ── Stripe Form Setup ──

  const stripeForm = useForm<{ country: string }>({
    defaultValues: { country: 'US' },
  })

  const [stripeLoading, setStripeLoading] = useState(false)

  const goToStripeOnboarding = useCallback(
    async (account: schemas['Account']) => {
      setStripeLoading(true)
      const returnPath = `/dashboard/${createdOrg?.slug}/finance/account`
      const { data, error } = await api.POST(
        '/api/accounts/{id}/onboarding_link',
        {
          params: {
            path: { id: account.id },
            query: { return_path: returnPath },
          },
        },
      )
      setStripeLoading(false)

      if (error) {
        window.location.href = `/dashboard/${createdOrg?.slug}`
        return
      }

      if (isSafeRedirect(data.url, ALLOWED_STRIPE_ORIGINS)) {
        window.location.href = data.url
      } else {
        window.location.href = `/dashboard/${createdOrg?.slug}`
      }
    },
    [createdOrg],
  )

  const onStripeSubmit = useCallback(
    async (data: { country: string }) => {
      if (!createdOrg) return
      setStripeLoading(true)

      const { data: account, error } = await api.POST('/api/accounts', {
        body: {
          account_type: 'stripe',
          country: data.country as schemas['StripeAccountCountry'],
          workspace_id: createdOrg.id,
        },
      })

      if (error) {
        if (isValidationError(error.detail)) {
          setValidationErrors(
            error.detail,
            stripeForm.setError as Parameters<typeof setValidationErrors>[1],
          )
        } else {
          stripeForm.setError('root', {
            message:
              typeof error.detail === 'string'
                ? error.detail
                : 'Failed to create account',
          })
        }
        setStripeLoading(false)
        return
      }

      await goToStripeOnboarding(account)
    },
    [createdOrg, goToStripeOnboarding, stripeForm],
  )

  // ── Navigation ──

  const skipStripe = () => {
    if (createdOrg) {
      router.push(`/dashboard/${createdOrg.slug}`)
    }
  }

  // ── Render ──

  return (
    <div className="md:rp-page-bg flex min-h-dvh flex-col pt-16 md:items-center md:p-16">
      <div className="flex min-h-0 w-full shrink-0 flex-col gap-12 md:max-w-xl md:p-8">
        {/* Header */}
        <motion.div initial="hidden" animate="visible">
          <FadeUp className="flex flex-col items-center gap-y-8">
            <Link href="/">
              <LogoIcon className="rp-text-primary" size={50} />
            </Link>
            <div className="flex flex-col items-center gap-y-4">
              {step === 'workspace' ? (
                <>
                  <h1 className="text-3xl">Let&rsquo;s get you started</h1>
                  <p className="text-lg text-slate-600 dark:text-slate-400">
                    You&rsquo;ll be up and running in no time
                  </p>
                </>
              ) : (
                <>
                  <h1 className="text-3xl">Connect Your Stripe Account</h1>
                  <p className="text-lg text-slate-600 dark:text-slate-400">
                    Connect a Stripe account to receive payments for your file
                    shares
                  </p>
                </>
              )}
            </div>

            {/* Step indicator */}
            <div className="flex items-center gap-x-3">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                  step === 'workspace'
                    ? 'bg-slate-700 text-white dark:bg-slate-300 dark:text-slate-900'
                    : 'bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                }`}
              >
                1
              </div>
              <div className="h-px w-8 bg-slate-300 dark:bg-slate-700" />
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                  step === 'stripe'
                    ? 'bg-slate-700 text-white dark:bg-slate-300 dark:text-slate-900'
                    : 'bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
                }`}
              >
                2
              </div>
            </div>
          </FadeUp>
        </motion.div>

        {/* Step 1: Create Workspace */}
        {step === 'workspace' && (
          <motion.div
            initial="hidden"
            animate="visible"
            transition={{ duration: 0.5, staggerChildren: 0.15 }}
            className="flex flex-col gap-12"
          >
            <Form {...orgForm}>
              <form
                onSubmit={handleOrgSubmit(onOrgSubmit)}
                className="flex w-full flex-col gap-y-8"
              >
                <div className="flex flex-col gap-y-8">
                  {/* Name & Slug */}
                  <FadeUp className="glass-card flex flex-col gap-y-4 rounded-3xl p-6">
                    <FormField
                      control={orgControl}
                      name="name"
                      rules={{
                        required: 'This field is required',
                      }}
                      render={({ field }) => (
                        <FormItem className="w-full">
                          <FormLabel htmlFor="name">Workspace Name</FormLabel>
                          <FormControl className="flex w-full flex-col gap-y-4">
                            <Input {...field} placeholder="Acme Inc." />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={orgControl}
                      name="slug"
                      rules={{
                        required: 'Slug is required',
                      }}
                      render={({ field }) => (
                        <FormItem className="w-full">
                          <FormLabel htmlFor="slug">Workspace Slug</FormLabel>
                          <FormControl className="flex w-full flex-col gap-y-4">
                            <Input
                              type="text"
                              {...field}
                              size={slug?.length || 1}
                              placeholder="acme-inc"
                              onFocus={() => setEditedSlug(true)}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={orgControl}
                      name="default_presentment_currency"
                      rules={{
                        required: 'Currency is required',
                      }}
                      render={({ field }) => (
                        <FormItem className="w-full">
                          <FormLabel htmlFor="default_presentment_currency">
                            Default Payment Currency
                          </FormLabel>
                          <FormControl className="flex w-full flex-col gap-y-4">
                            <CurrencySelector
                              value={
                                field.value as schemas['PresentmentCurrency']
                              }
                              onChange={field.onChange}
                            />
                          </FormControl>
                          <FormMessage />
                          <FormDescription>
                            The default currency for your products
                          </FormDescription>
                        </FormItem>
                      )}
                    />
                  </FadeUp>

                  {/* Supported Use Cases */}
                  <FadeUp className="glass-card flex flex-col gap-y-4 rounded-3xl p-6">
                    <SupportedUseCases />
                  </FadeUp>

                  {/* Terms & Compliance */}
                  <FadeUp className="glass-card flex flex-col gap-y-4 rounded-3xl p-6">
                    <FormField
                      control={orgControl}
                      name="terms"
                      rules={{
                        required: 'You must accept the terms to continue',
                      }}
                      render={({ field }) => {
                        return (
                          <FormItem>
                            <div className="flex flex-row items-start gap-x-3">
                              <Checkbox
                                id="terms"
                                checked={field.value}
                                onCheckedChange={(checked: boolean) => {
                                  const value = checked ? true : false
                                  setOrgValue('terms', value)
                                }}
                                className="mt-1"
                              />
                              <div className="flex flex-col gap-y-2 text-sm">
                                <label
                                  htmlFor="terms"
                                  className="cursor-pointer leading-relaxed font-medium"
                                >
                                  I understand the restrictions above and agree
                                  to the terms
                                </label>
                                <ul className="flex flex-col gap-y-1 text-sm text-slate-500 dark:text-slate-400">
                                  <li>
                                    <a
                                      href={`${CONFIG.DOCS_BASE_URL}/account-reviews`}
                                      className="text-slate-600 hover:underline dark:text-slate-400"
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      Account Reviews Policy
                                    </a>
                                    {' - '}I&apos;ll comply with KYC/AML
                                    requirements including website and social
                                    verification
                                  </li>
                                  <li>
                                    <a
                                      href={CONFIG.LEGAL_TERMS_URL}
                                      className="text-slate-600 hover:underline dark:text-slate-400"
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      Terms of Service
                                    </a>
                                  </li>
                                  <li>
                                    <a
                                      href={CONFIG.LEGAL_PRIVACY_URL}
                                      className="text-slate-600 hover:underline dark:text-slate-400"
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      Privacy Policy
                                    </a>
                                  </li>
                                </ul>
                              </div>
                            </div>
                            <FormMessage />
                          </FormItem>
                        )
                      }}
                    />
                  </FadeUp>

                  {/* Cookie Consent */}
                  <FadeUp className="glass-card flex flex-col gap-y-4 rounded-3xl p-6">
                    <FormField
                      control={orgControl}
                      name="cookie_consent"
                      rules={{
                        required:
                          'You must accept analytics cookies to continue',
                      }}
                      render={({ field }) => (
                        <FormItem>
                          <div className="flex flex-row items-start gap-x-3">
                            <Checkbox
                              id="cookie_consent"
                              checked={field.value}
                              onCheckedChange={(checked: boolean) =>
                                setOrgValue('cookie_consent', !!checked)
                              }
                              className="mt-1"
                            />
                            <label
                              htmlFor="cookie_consent"
                              className="cursor-pointer text-sm leading-relaxed font-medium"
                            >
                              I agree to the use of analytics cookies to help
                              improve the product experience
                            </label>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </FadeUp>
                </div>

                {orgErrors.root && (
                  <p className="text-destructive-foreground text-sm">
                    {orgErrors.root.message}
                  </p>
                )}

                <FadeUp className="flex flex-col gap-y-3">
                  <Button
                    type="submit"
                    loading={createWorkspace.isPending}
                    disabled={
                      name.length === 0 ||
                      slug.length === 0 ||
                      !terms ||
                      !watchOrg('cookie_consent')
                    }
                  >
                    Continue
                  </Button>
                  <Link
                    href={`${CONFIG.BASE_URL}/api/auth/logout`}
                    prefetch={false}
                    className="w-full"
                  >
                    <Button variant="secondary" fullWidth>
                      Logout
                    </Button>
                  </Link>
                </FadeUp>
              </form>
            </Form>
          </motion.div>
        )}

        {/* Step 2: Connect Stripe */}
        {step === 'stripe' && (
          <motion.div
            initial="hidden"
            animate="visible"
            transition={{ duration: 0.5, staggerChildren: 0.15 }}
            className="flex flex-col gap-12"
          >
            <Form {...stripeForm}>
              <form
                onSubmit={stripeForm.handleSubmit(onStripeSubmit)}
                className="flex w-full flex-col gap-y-8"
              >
                <FadeUp className="glass-card flex flex-col gap-y-4 rounded-3xl p-6">
                  <FormField
                    control={stripeForm.control}
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
                        <FormDescription>
                          If this is a personal account, select your country of
                          residence. For a business, select the country of
                          incorporation.
                        </FormDescription>
                      </FormItem>
                    )}
                  />
                </FadeUp>

                {stripeForm.formState.errors.root && (
                  <p className="text-destructive-foreground text-sm">
                    {stripeForm.formState.errors.root.message}
                  </p>
                )}

                <FadeUp className="flex flex-col gap-y-3">
                  {stripeLoading && (
                    <p className="text-center text-sm text-slate-500 dark:text-slate-400">
                      Setting up your Stripe account&hellip; This may take a few
                      seconds.
                    </p>
                  )}
                  <Button
                    type="submit"
                    loading={stripeLoading}
                    disabled={stripeLoading}
                  >
                    Connect Stripe Account
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={skipStripe}
                    disabled={stripeLoading}
                    fullWidth
                  >
                    Skip for now
                  </Button>
                </FadeUp>
              </form>
            </Form>
          </motion.div>
        )}
      </div>
    </div>
  )
}

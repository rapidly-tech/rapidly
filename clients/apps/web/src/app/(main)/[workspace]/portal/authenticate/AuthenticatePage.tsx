'use client'

import { useCustomerPortalSessionAuthenticate } from '@/hooks/api'
import { setValidationErrors } from '@/utils/api/errors'
import { getQueryClient } from '@/utils/api/query'
import { api } from '@/utils/client'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from '@rapidly-tech/ui/components/forms/InputOTP'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useCallback } from 'react'
import { useForm, useWatch } from 'react-hook-form'
const ClientPage = ({
  workspace,
}: {
  workspace: schemas['CustomerWorkspace']
}) => {
  const router = useRouter()
  const form = useForm<{ code: string }>()
  const { control, handleSubmit, setError } = form
  const sessionRequest = useCustomerPortalSessionAuthenticate(api)

  const code = useWatch({ control, name: 'code', defaultValue: '' })

  const onSubmit = useCallback(
    async ({ code }: { code: string }) => {
      const { data, error } = await sessionRequest.mutateAsync({ code })

      if (error && error?.detail) {
        if (typeof error.detail === 'string') {
          setError('root', { message: error.detail })
        } else {
          setValidationErrors(error.detail, setError)
        }
        return
      }

      if (!data) {
        setError('root', { message: 'Invalid verification code' })
        return
      }

      // Invalidate cached queries before redirect to ensure fresh data
      const queryClient = getQueryClient()
      queryClient.invalidateQueries({ queryKey: ['portal_authenticated_user'] })
      queryClient.invalidateQueries({ queryKey: ['customer_portal_session'] })
      queryClient.invalidateQueries({ queryKey: ['customer'] })

      router.push(
        `/${workspace.slug}/portal/?customer_session_token=${data.token}`,
      )
    },
    [sessionRequest, setError, router, workspace],
  )

  return (
    <div className="relative z-10 flex w-full max-w-xl flex-col gap-y-1 rounded-3xl bg-slate-100 p-1 shadow-[0_8px_40px_rgba(0,0,0,0.06)] dark:border dark:border-slate-900 dark:bg-slate-950">
      {/* Title bar */}
      <div className="flex flex-row items-center justify-between pt-1 pr-1 pb-0 pl-4 text-sm">
        <span className="text-slate-500">Verification</span>
        <Link
          href={`/${workspace.slug}/portal/request`}
          className="inline-flex size-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-400"
          aria-label="Close"
        >
          <Icon icon="solar:close-circle-linear" className="text-[1em]" />
        </Link>
      </div>

      {/* Content area */}
      <div className="flex flex-col items-center gap-12 rounded-[20px] bg-white p-12 md:px-20 md:py-16 dark:bg-white/5 dark:backdrop-blur-[60px]">
        <div className="flex w-full flex-col gap-y-6 md:max-w-sm">
          <div className="flex flex-col gap-4">
            <h2 className="rp-text-primary text-2xl">Verification code</h2>
            <p className="text-slate-500 dark:text-slate-400">
              Enter the verification code sent to your email address.
            </p>
          </div>
          <Form {...form}>
            <form
              className="flex w-full flex-col items-center gap-y-6"
              onSubmit={handleSubmit(onSubmit)}
            >
              <FormField
                control={control}
                name="code"
                render={({
                  field,
                }: {
                  field: {
                    value: string
                    onChange: (value: string) => void
                    onBlur: () => void
                    name: string
                    ref: React.Ref<HTMLInputElement>
                  }
                }) => {
                  return (
                    <FormItem>
                      <FormControl>
                        <InputOTP
                          maxLength={6}
                          pattern="^[a-zA-Z0-9]+$"
                          inputMode="text"
                          {...field}
                          onChange={(value: string) =>
                            field.onChange(value.toUpperCase())
                          }
                        >
                          <InputOTPGroup>
                            {Array.from({ length: 6 }).map((_, index) => (
                              <InputOTPSlot
                                key={`otp-slot-${index}`}
                                index={index}
                                className="h-12 w-12 border-slate-300 text-xl md:h-16 md:w-16 md:text-2xl dark:border-slate-700"
                              />
                            ))}
                          </InputOTPGroup>
                        </InputOTP>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )
                }}
              />

              {form.formState.errors.root && (
                <p className="text-sm font-medium text-red-500 dark:text-red-400">
                  {form.formState.errors.root.message}
                </p>
              )}

              <Button
                type="submit"
                size="lg"
                className="w-full"
                loading={sessionRequest.isPending}
                disabled={sessionRequest.isPending || code.length !== 6}
              >
                Access my files
              </Button>

              <p className="text-sm text-slate-500 dark:text-slate-400">
                Don&apos;t have a code?{' '}
                <Link href="request" className="underline hover:no-underline">
                  Request a new one
                </Link>
                .
              </p>
            </form>
          </Form>
        </div>
      </div>
    </div>
  )
}

export default ClientPage

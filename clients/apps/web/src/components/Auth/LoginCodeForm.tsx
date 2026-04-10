'use client'

import { LoginCodeError, useSendLoginCode } from '@/hooks/loginCode'
import { usePostHog, type EventName } from '@/hooks/posthog'
import { setValidationErrors } from '@/utils/api/errors'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { useCallback, useState } from 'react'
import { SubmitHandler, useForm } from 'react-hook-form'

interface LoginCodeFormProps {
  returnTo?: string
  signup?: schemas['UserSignupAttribution']
}

/**
 * Email-based passwordless login form.
 * Sends a one-time login code to the provided email address.
 */
const LoginCodeForm = ({ returnTo, signup }: LoginCodeFormProps) => {
  const form = useForm<{ email: string }>()
  const { handleSubmit, setError } = form
  const [loading, setLoading] = useState(false)
  const sendLoginCode = useSendLoginCode()
  const posthog = usePostHog()

  const onSubmit: SubmitHandler<{ email: string }> = useCallback(
    async ({ email }) => {
      setLoading(true)
      const eventName: EventName = signup
        ? 'global:user:signup:submit'
        : 'global:user:login:submit'

      posthog.capture(eventName, { method: 'code' })

      try {
        await sendLoginCode(email, returnTo, signup)
      } catch (e) {
        if (e instanceof LoginCodeError && e.error) {
          setValidationErrors(e.error, setError)
        }
      } finally {
        setLoading(false)
      }
    },
    [posthog, signup, sendLoginCode, returnTo, setError],
  )

  return (
    <Form {...form}>
      <form className="flex w-full flex-col" onSubmit={handleSubmit(onSubmit)}>
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormControl className="w-full">
                <div className="flex w-full flex-row gap-2">
                  <Input
                    type="email"
                    required
                    placeholder="Email"
                    autoComplete="off"
                    data-1p-ignore
                    {...field}
                  />
                  <Button
                    type="submit"
                    variant="secondary"
                    loading={loading}
                    disabled={loading}
                  >
                    Login
                  </Button>
                </div>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </form>
    </Form>
  )
}

export default LoginCodeForm

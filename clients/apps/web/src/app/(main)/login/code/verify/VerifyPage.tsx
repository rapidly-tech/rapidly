'use client'

import { CONFIG } from '@/utils/config'
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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'

const CODE_LENGTH = 6
const CODE_TTL_SECONDS = 10 * 60
const CODE_PATTERN = '^[a-zA-Z0-9]+$'

const SLOT_CLASSES =
  'dark:border-slate-700 h-12 w-12 border-slate-300 text-xl md:h-16 md:w-16 md:text-2xl'

const buildFormAction = (baseUrl: string, params: URLSearchParams): string =>
  `${baseUrl}/api/login-code/authenticate?${params.toString()}`

const normalizeCode = (value: string): string => value.toUpperCase()

const OTPSlots = () => (
  <InputOTPGroup>
    {Array.from({ length: CODE_LENGTH }).map((_, idx) => (
      <InputOTPSlot key={idx} index={idx} className={SLOT_CLASSES} />
    ))}
  </InputOTPGroup>
)

const ClientPage = ({
  return_to,
  error,
  email,
}: {
  return_to?: string
  error?: string
  email?: string
}) => {
  const form = useForm<{ code: string }>()
  const { control, setError } = form
  const formRef = useRef<HTMLFormElement>(null)
  const [loading, setLoading] = useState(false)
  const [secondsLeft, setSecondsLeft] = useState(CODE_TTL_SECONDS)

  useEffect(() => {
    if (secondsLeft <= 0) return
    const timer = setInterval(() => setSecondsLeft((s) => s - 1), 1000)
    return () => clearInterval(timer)
  }, [secondsLeft])

  const urlSearchParams = useMemo(
    () =>
      new URLSearchParams({
        ...(return_to && { return_to }),
        ...(email && { email }),
      }),
    [return_to, email],
  )

  const formAction = useMemo(
    () => buildFormAction(CONFIG.BASE_URL, urlSearchParams),
    [urlSearchParams],
  )

  useEffect(() => {
    if (error) {
      setError('code', { message: error })
    }
  }, [error, setError])

  const handleSubmit = useCallback((e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setLoading(true)
    e.currentTarget.submit()
  }, [])

  const handleComplete = useCallback(() => {
    if (formRef.current) {
      setLoading(true)
      formRef.current.submit()
    }
  }, [])

  return (
    <Form {...form}>
      <form
        ref={formRef}
        className="flex w-full flex-col items-center gap-y-6"
        action={formAction}
        method="POST"
        onSubmit={handleSubmit}
      >
        <div className="mb-2 text-center text-xs text-slate-400 dark:text-slate-500">
          {secondsLeft > 0
            ? `Code expires in ${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, '0')}`
            : 'Code expired'}
        </div>
        <FormField
          control={control}
          name="code"
          render={({ field }) => (
            <FormItem>
              <FormControl>
                <InputOTP
                  maxLength={CODE_LENGTH}
                  pattern={CODE_PATTERN}
                  inputMode="text"
                  {...field}
                  autoFocus={true}
                  onChange={(value) => field.onChange(normalizeCode(value))}
                  onComplete={handleComplete}
                >
                  <OTPSlots />
                </InputOTP>
              </FormControl>
              <FormMessage className="text-center" />
            </FormItem>
          )}
        />
        <Button type="submit" size="lg" className="w-full" loading={loading}>
          Sign in
        </Button>
      </form>
    </Form>
  )
}

export default ClientPage

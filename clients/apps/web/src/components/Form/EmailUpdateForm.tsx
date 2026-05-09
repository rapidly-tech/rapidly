'use client'

import { useSendEmailUpdate } from '@/hooks/emailUpdate'
import { setValidationErrors } from '@/utils/api/errors'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
} from '@rapidly-tech/ui/components/primitives/form'
import { useCallback, useState } from 'react'
import { SubmitHandler, useForm } from 'react-hook-form'

interface EmailUpdateformProps {
  returnTo?: string
  onEmailUpdateRequest?: () => void
  onCancel?: () => void
}

const DEFAULT_ERROR_MSG = 'An error occurred while updating your email.'

const extractEmailErrorMessage = (
  detail: schemas['ValidationError'][],
): string => {
  const emailDetail = detail.find(
    (err) => Array.isArray(err.loc) && err.loc.includes('email'),
  )
  return emailDetail?.msg ?? DEFAULT_ERROR_MSG
}

const ErrorBanner = ({ message }: { message: string }) => (
  <div className="text-sm text-red-700 dark:text-red-500">{message}</div>
)

const CancelButton = ({
  onClick,
  disabled,
}: {
  onClick: () => void
  disabled: boolean
}) => (
  <Button
    type="button"
    size="lg"
    variant="ghost"
    onClick={onClick}
    disabled={disabled}
  >
    Cancel
  </Button>
)

const EmailUpdateForm: React.FC<EmailUpdateformProps> = ({
  returnTo,
  onEmailUpdateRequest,
  onCancel,
}) => {
  const form = useForm<{ email: string }>()
  const { handleSubmit, setError } = form
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const sendEmailUpdate = useSendEmailUpdate()

  const clearError = useCallback(() => setErrorMessage(null), [])

  const onSubmit: SubmitHandler<{ email: string }> = useCallback(
    async ({ email }) => {
      clearError()
      setLoading(true)

      const { error } = await sendEmailUpdate(email, returnTo)
      setLoading(false)

      if (error) {
        if (error.detail && Array.isArray(error.detail)) {
          setErrorMessage(extractEmailErrorMessage(error.detail))
          setValidationErrors(error.detail, setError)
        } else {
          setErrorMessage(DEFAULT_ERROR_MSG)
        }
        return
      }

      onEmailUpdateRequest?.()
    },
    [clearError, sendEmailUpdate, returnTo, setError, onEmailUpdateRequest],
  )

  const showCancel = Boolean(onCancel)

  return (
    <Form {...form}>
      <form
        className="flex w-full flex-col gap-2"
        onSubmit={handleSubmit(onSubmit)}
      >
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
                    placeholder="New email"
                    autoComplete="off"
                    data-1p-ignore
                    {...field}
                  />
                  <Button
                    type="submit"
                    size="lg"
                    variant="secondary"
                    loading={loading}
                    disabled={loading}
                  >
                    Update
                  </Button>
                  {showCancel && onCancel && (
                    <CancelButton onClick={onCancel} disabled={loading} />
                  )}
                </div>
              </FormControl>
            </FormItem>
          )}
        />
        {errorMessage && <ErrorBanner message={errorMessage} />}
      </form>
    </Form>
  )
}

export default EmailUpdateForm

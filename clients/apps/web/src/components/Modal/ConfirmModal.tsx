import Button from '@rapidly-tech/ui/components/forms/Button'
import Input from '@rapidly-tech/ui/components/forms/Input'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@rapidly-tech/ui/components/primitives/form'
import { useCallback, type MouseEvent } from 'react'
import { useForm, type Control } from 'react-hook-form'
import { Modal, ModalProps } from '.'

export interface ConfirmModalProps extends Omit<
  ModalProps,
  'title' | 'modalContent'
> {
  title: string
  description?: string
  body?: React.ReactNode
  destructive?: boolean
  destructiveText?: string
  confirmPrompt?: string
  onConfirm: () => void
  onCancel?: () => void
}

function PromptField({
  control,
  expectedValue,
}: {
  control: Control<{ prompt?: string }>
  expectedValue: string
}) {
  return (
    <>
      <p className="max-w-full text-sm text-slate-500 dark:text-slate-400">
        Please enter &quot;{expectedValue}&quot; to confirm:
      </p>
      <FormField
        control={control}
        name="prompt"
        rules={{
          validate: (val: string | undefined) =>
            val === expectedValue || 'Please enter the exact text to confirm',
        }}
        render={({ field }) => (
          <FormItem>
            <FormControl className="w-full">
              <Input
                type="input"
                required
                placeholder={expectedValue}
                autoComplete="off"
                {...field}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    </>
  )
}

export const ConfirmModal = ({
  title,
  description,
  body,
  destructive,
  destructiveText = 'Delete',
  confirmPrompt,
  onConfirm,
  onCancel,
  ...modalProps
}: ConfirmModalProps) => {
  const form = useForm<{ prompt?: string }>({ defaultValues: { prompt: '' } })
  const { handleSubmit, reset, watch } = form

  const typedPrompt = watch('prompt')
  const isPromptValid = confirmPrompt ? typedPrompt === confirmPrompt : true

  const confirmAndClose = useCallback(() => {
    onConfirm()
    reset()
    modalProps.hide()
  }, [onConfirm, modalProps, reset])

  const cancelAndClose = useCallback(
    (e: MouseEvent<HTMLButtonElement>) => {
      e.preventDefault()
      reset()
      onCancel?.()
      modalProps.hide()
    },
    [onCancel, modalProps, reset],
  )

  const submitLabel = destructive ? destructiveText : 'Confirm'
  const submitVariant = destructive ? 'destructive' : 'default'

  return (
    <Modal
      title={title}
      className="md:min-w-[300px] lg:max-w-[600px]"
      {...modalProps}
      modalContent={
        <div className="flex flex-col gap-y-4 p-8">
          <h3 className="text-xl font-medium">{title}</h3>

          {description && (
            <p className="max-w-full text-sm text-slate-500 dark:text-slate-400">
              {description}
            </p>
          )}

          {body}

          <Form {...form}>
            <form
              className="flex w-full flex-col gap-y-2"
              onSubmit={handleSubmit(confirmAndClose)}
            >
              {confirmPrompt && (
                <PromptField
                  control={form.control}
                  expectedValue={confirmPrompt}
                />
              )}

              <div className="flex flex-row-reverse gap-x-4 pt-2">
                <Button
                  type="submit"
                  variant={submitVariant}
                  disabled={!isPromptValid}
                >
                  {submitLabel}
                </Button>
                <Button variant="ghost" onClick={cancelAndClose}>
                  Cancel
                </Button>
              </div>
            </form>
          </Form>
        </div>
      }
    />
  )
}

import { schemas } from '@rapidly-tech/client'
import { FieldPath, FieldValues, UseFormSetError } from 'react-hook-form'

// ── Form Error Binding ──

export const setValidationErrors = <T extends FieldValues>(
  errors: schemas['ValidationError'][],
  setError: UseFormSetError<T>,
  slice: number = 1,
  discriminators?: string[],
): void => {
  for (const err of errors) {
    let segments = err.loc.slice(slice)
    if (discriminators?.includes(segments[0] as string)) {
      segments = segments.slice(1)
    }
    setError(segments.join('.') as FieldPath<T>, {
      type: err.type,
      message: err.msg,
    })
  }
}

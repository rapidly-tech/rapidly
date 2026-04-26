// URL parameter keys for each toast category
const PARAM_KEYS = {
  status: { name: 'status', desc: 'status_description' },
  error: { name: 'error', desc: 'error_description' },
} as const

type ToastCategory = keyof typeof PARAM_KEYS

function buildToastURL(
  basePath: string,
  category: ToastCategory,
  title: string,
  description: string,
  disableButton: boolean,
  extraParams: string,
): string {
  const { name, desc } = PARAM_KEYS[category]
  const url = new URL(basePath, 'http://placeholder')

  url.searchParams.set('toast', 'true')
  url.searchParams.set(name, title)

  if (description) url.searchParams.set(desc, description)
  if (disableButton) url.searchParams.set('disable_button', 'true')

  // Reconstruct with the original path (drop the placeholder origin)
  let result = `${basePath}?${url.searchParams.toString()}`

  if (extraParams) result += `&${extraParams}`

  return result
}

export const getStatusRedirect = (
  path: string,
  statusName: string,
  statusDescription: string = '',
  disableButton: boolean = false,
  arbitraryParams: string = '',
) =>
  buildToastURL(
    path,
    'status',
    statusName,
    statusDescription,
    disableButton,
    arbitraryParams,
  )

export const getErrorRedirect = (
  path: string,
  errorName: string,
  errorDescription: string = '',
  disableButton: boolean = false,
  arbitraryParams: string = '',
) =>
  buildToastURL(
    path,
    'error',
    errorName,
    errorDescription,
    disableButton,
    arbitraryParams,
  )

export {
  createPortalClient,
  type PortalClient,
  type PortalClientConfig,
} from './client'

export {
  RapidlyCustomerPortalError,
  RateLimitError,
  UnauthorizedError,
  ValidationError,
  isValidationError,
  type ValidationErrorItem,
} from './errors'

export { customerPortalKeys } from './keys'

export type {
  CustomerPortalCustomer,
  CustomerPortalCustomerUpdate,
} from './types'

export { createCustomerMethods } from './customer'

import { operations } from '@rapidly-tech/client'

type AuthorizeSuccessResponse =
  operations['oauth2:authorize']['responses']['200']['content']['application/json']

export type AuthorizeResponse = AuthorizeSuccessResponse

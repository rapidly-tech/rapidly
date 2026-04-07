import { getQueryClient } from '@/utils/api/query'
import { api } from '@/utils/client'
import { operations, resolveResponse, schemas } from '@rapidly-tech/client'
import { useMutation, useQuery } from '@tanstack/react-query'

/** Fetches the list of registered OAuth2 clients. */
export const useOAuth2Clients = (
  options?: operations['oauth2:list']['parameters']['query'],
) =>
  useQuery({
    queryKey: ['oauth2Clients', options],
    queryFn: async () =>
      resolveResponse(api.GET('/api/oauth2/', { params: { query: options } })),
  })

/** Registers a new OAuth2 client. */
export const useCreateOAuth2Client = () =>
  useMutation({
    mutationFn: (body: schemas['OAuth2ClientConfiguration']) =>
      api.POST('/api/oauth2/register', { body }),
    onSuccess(data, _variables, _context) {
      if (data.error) {
        return
      }
      getQueryClient().invalidateQueries({
        queryKey: ['oauth2Clients'],
      })
    },
  })

/** Updates an existing OAuth2 client's configuration. */
export const useUpdateOAuth2Client = () =>
  useMutation({
    mutationFn: ({
      client_id,
      body,
    }: {
      client_id: string
      body: schemas['OAuth2ClientConfigurationUpdate']
    }) =>
      api.PUT('/api/oauth2/register/{client_id}', {
        params: { path: { client_id } },
        body,
      }),
    onSuccess(data, _variables, _context) {
      if (data.error) {
        return
      }
      getQueryClient().invalidateQueries({
        queryKey: ['oauth2Clients'],
      })
    },
  })

/** Deletes an OAuth2 client by its client ID. */
export const useDeleteOAuthClient = () =>
  useMutation({
    mutationFn: (clientId: string) =>
      api.DELETE('/api/oauth2/register/{client_id}', {
        params: { path: { client_id: clientId } },
      }),
    onSuccess(data, _variables, _context) {
      if (data.error) {
        return
      }
      getQueryClient().invalidateQueries({
        queryKey: ['oauth2Clients'],
      })
    },
  })

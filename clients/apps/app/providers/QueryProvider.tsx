/**
 * TanStack Query client wrapper with React Query devtools integration.
 */
import { queryClient, QueryClientProvider } from '@/utils/query'
import { useReactQueryDevTools } from '@dev-plugins/react-query'

export function QueryProvider({ children }: { children: React.ReactElement }) {
  useReactQueryDevTools(queryClient)

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

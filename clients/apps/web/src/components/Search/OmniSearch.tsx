'use client'

import {
  useGeneralRoutes,
  useWorkspaceRoutes,
} from '@/components/Dashboard/navigation'
import { api } from '@/utils/client'
import { Icon } from '@iconify/react'
import * as Dialog from '@radix-ui/react-dialog'
import { resolveResponse, schemas } from '@rapidly-tech/client'
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@rapidly-tech/ui/components/primitives/command'
import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { twMerge } from 'tailwind-merge'
import { Result } from './components/Result'
import type { SearchResult, SearchResultPage } from './types'

// ── Types ──

interface OmniSearchProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspace: schemas['Workspace']
}

/** Command palette search dialog for navigating pages, quick actions, files, and customers. */
export const OmniSearch = ({
  open,
  onOpenChange,
  workspace,
}: OmniSearchProps) => {
  // ── State ──
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)

  // ── Routes & Quick Actions ──
  const generalRoutes = useGeneralRoutes(workspace)
  const orgRoutes = useWorkspaceRoutes(workspace)
  const allRoutes = useMemo(
    () => [...generalRoutes, ...orgRoutes],
    [generalRoutes, orgRoutes],
  )

  const pageResults = useMemo(() => {
    if (!query.trim()) return []

    const searchLower = query.toLowerCase()
    const pages: SearchResultPage[] = []

    allRoutes.forEach((route) => {
      if (route.title.toLowerCase().includes(searchLower)) {
        pages.push({
          id: route.id,
          type: 'page',
          title: route.title,
          url: route.link,
          icon: route.icon,
        })
      }

      route.subs?.forEach((sub) => {
        if (sub.title.toLowerCase().includes(searchLower)) {
          pages.push({
            id: `${route.id}-${sub.title}`,
            type: 'page',
            title: `${route.title} \u2192 ${sub.title}`,
            url: sub.link,
            icon: sub.icon || route.icon,
          })
        }
      })
    })

    return pages.slice(0, 5)
  }, [query, allRoutes])

  // ── Search Logic ──
  const performSearch = useCallback(
    async (searchQuery: string, signal: AbortSignal) => {
      if (!searchQuery.trim()) {
        setResults([])
        setHasSearched(false)
        return
      }

      const loadingTimer = setTimeout(() => setLoading(true), 150)
      try {
        const data = await resolveResponse(
          api.GET('/search', {
            params: {
              query: {
                workspace_id: workspace.id,
                query: searchQuery,
                limit: 5,
              },
            },
            signal,
          }),
        )
        setResults(data.results as SearchResult[])
        setHasSearched(true)
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          return
        }
        setResults([])
        setHasSearched(true)
      } finally {
        clearTimeout(loadingTimer)
        setLoading(false)
      }
    },
    [workspace.id],
  )

  const combinedResults = useMemo(() => {
    return [...pageResults, ...results]
  }, [pageResults, results])

  useEffect(() => {
    const controller = new AbortController()
    const debounce = setTimeout(() => {
      performSearch(query, controller.signal)
    }, 400)

    return () => {
      clearTimeout(debounce)
      controller.abort()
    }
  }, [query, performSearch])

  // ── Handlers ──
  const handleSelect = (result: SearchResult) => {
    let path = ''

    switch (result.type) {
      case 'action':
      case 'page':
        path = result.url
        break
      case 'share':
        path = `/dashboard/${workspace.slug}/files/${result.id}`
        break
      case 'customer':
        path = `/dashboard/${workspace.slug}/customers/${result.id}`
        break
    }

    if (path) {
      router.push(path)
      onOpenChange(false)
      setQuery('')
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'action':
        return 'Quick Action'
      case 'page':
        return 'Go to'
      case 'share':
        return 'Files'
      case 'customer':
        return 'Customers'
      default:
        return type
    }
  }

  // ── Result Grouping & Rendering ──
  const groupedResults: Record<string, SearchResult[]> = useMemo(
    () =>
      combinedResults.reduce(
        (acc, result) => {
          if (!acc[result.type]) {
            acc[result.type] = []
          }
          acc[result.type].push(result)
          return acc
        },
        {} as Record<string, SearchResult[]>,
      ),
    [combinedResults],
  )

  const renderResult = (result: SearchResult) => {
    switch (result.type) {
      case 'action':
        return <Result icon={result.icon} title={result.title} />
      case 'page':
        return <Result icon={result.icon} title={result.title} />
      case 'share':
        return (
          <Result
            title={result.name}
            description={result.description || undefined}
          />
        )
      case 'customer':
        return (
          <Result
            title={result.name || result.email}
            description={result.name ? result.email : undefined}
          />
        )
    }
  }

  // ── Render ──
  const cleanState =
    !query || (!loading && !hasSearched && combinedResults.length === 0)

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-bottom-4 data-[state=open]:slide-in-from-bottom-4 fixed top-[15%] left-[50%] z-50 w-full max-w-2xl translate-x-[-50%] overflow-hidden rounded-xl border border-slate-200/80 bg-white p-0 shadow-2xl ring-1 ring-black/5 dark:border-slate-900/80 dark:bg-slate-950 dark:ring-white/5">
          <Dialog.DialogTitle className="sr-only">Search</Dialog.DialogTitle>
          <Command
            className="**:[[cmdk-group-heading]]:text-xxs rounded-xl border-none [&_[cmdk-group]:not([hidden])_~[cmdk-group]]:pt-0 **:[[cmdk-group-heading]]:px-0 **:[[cmdk-group-heading]]:py-2 **:[[cmdk-group-heading]]:font-medium **:[[cmdk-group-heading]]:tracking-wider **:[[cmdk-group-heading]]:text-slate-500! **:[[cmdk-group-heading]]:uppercase dark:**:[[cmdk-group-heading]]:text-slate-400! **:[[cmdk-group]]:px-3 **:[[cmdk-input-wrapper]_svg]:h-5 **:[[cmdk-input-wrapper]_svg]:w-5 **:[[cmdk-input]]:h-14 **:[[cmdk-item]_svg]:h-5 **:[[cmdk-item]_svg]:w-5 **:[[cmdk-item]]:px-2 **:[[cmdk-item]]:py-3"
            shouldFilter={false}
          >
            <div className="flex grow items-center px-4">
              <CommandInput
                placeholder="Search..."
                value={query}
                onValueChange={setQuery}
                wrapperClassName="border-none grow"
                className="flex w-full grow border-0 text-base placeholder:text-slate-400 focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 dark:placeholder:text-slate-500"
              />
            </div>

            <CommandList
              className={twMerge(
                'max-h-[420px] overflow-y-auto border-t border-slate-200 px-0 pt-2 pb-3 dark:border-slate-800',
                cleanState ? 'hidden' : '',
              )}
            >
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <Icon
                    icon="solar:refresh-circle-linear"
                    className="h-6 w-6 animate-spin text-slate-500"
                  />
                </div>
              ) : !loading &&
                hasSearched &&
                query &&
                combinedResults.length === 0 ? (
                <div className="py-12 text-center text-sm text-slate-500">
                  No results found for &quot;{query}&quot;
                </div>
              ) : (
                <>
                  {Object.entries(groupedResults).map(
                    ([type, typeResults], index) => {
                      const isLastGroup =
                        index === Object.entries(groupedResults).length - 1
                      return (
                        <CommandGroup
                          key={type}
                          heading={getTypeLabel(type)}
                          className={twMerge(
                            'p-0',
                            isLastGroup ? 'mb-0' : 'mb-2',
                          )}
                        >
                          {typeResults.map((result, resultIndex) => {
                            const key = `${result.type}-${result.id}`
                            const isFirst = index === 0 && resultIndex === 0
                            const isLastItem =
                              isLastGroup &&
                              resultIndex === typeResults.length - 1
                            return (
                              <CommandItem
                                key={key}
                                value={key}
                                onSelect={() => handleSelect(result)}
                                className={twMerge(
                                  'group rp-text-primary cursor-pointer rounded-xl px-3 py-3 data-[selected=true]:bg-slate-50 data-[selected=true]:text-inherit dark:data-[selected=true]:bg-slate-900',
                                  isFirst ? 'scroll-mt-12' : '',
                                  isLastItem
                                    ? 'mb-3 scroll-mb-12'
                                    : resultIndex < typeResults.length - 1
                                      ? 'mb-1'
                                      : '',
                                )}
                              >
                                {renderResult(result)}
                              </CommandItem>
                            )
                          })}
                        </CommandGroup>
                      )
                    },
                  )}
                </>
              )}
            </CommandList>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

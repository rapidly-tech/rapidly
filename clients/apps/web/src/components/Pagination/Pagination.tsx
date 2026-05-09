import Paginator from '@rapidly-tech/ui/components/navigation/Paginator'
import {
  ReadonlyURLSearchParams,
  useRouter,
  useSearchParams,
} from 'next/navigation'
import {
  type PropsWithChildren,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

interface PaginationProps extends PropsWithChildren {
  totalCount: number
  pageSize: number
  currentPage: number
  siblingCount?: number
  onPageChange: (page: number) => void
  className?: string
  currentURL: ReadonlyURLSearchParams | URLSearchParams
}

const Pagination = ({ children, ...navProps }: PaginationProps) => (
  <div className="flex flex-col gap-y-12">
    <div className="flex flex-col">{children}</div>
    <Paginator {...navProps} />
  </div>
)

export default Pagination

// Reads initial page from URL, syncs changes back via router.replace
function parseInitialPage(params: URLSearchParams | null): number {
  const raw = params?.get('page')
  return raw ? Number(raw) || 1 : 1
}

export const usePagination = () => {
  const router = useRouter()
  const params = useSearchParams()

  const startPage = useMemo(() => parseInitialPage(params), [params])
  const [currentPage, setPage] = useState(startPage)

  // Reset to page 1 when the search param disappears (e.g. filter change)
  useEffect(() => {
    if (!params?.has('page')) setPage(1)
  }, [params])

  const navigateToPage = useCallback(
    (page: number) => {
      if (!params) return
      setPage(page)

      const next = new URLSearchParams(params)
      next.set('page', String(page))

      const { pathname } = new URL(window.location.href)
      router.replace(`${pathname}?${next.toString()}`, { scroll: false })
    },
    [router, params],
  )

  return { currentPage, setCurrentPage: navigateToPage }
}

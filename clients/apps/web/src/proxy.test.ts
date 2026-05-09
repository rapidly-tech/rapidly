import { unstable_doesMiddlewareMatch } from 'next/experimental/testing/server'
import { NextRequest } from 'next/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { config, proxy } from './proxy'

vi.mock('./utils/client', () => ({
  buildServerAPI: vi.fn(),
}))

const nextConfig = {}

const expectMatchesMiddleware = (url: string, shouldMatch: boolean) =>
  expect(unstable_doesMiddlewareMatch({ config, nextConfig, url })).toBe(
    shouldMatch,
  )

const createRequest = (path: string): NextRequest =>
  new NextRequest(`https://example.com${path}`)

describe('proxy matcher configuration', () => {
  const matchingRoutes = [
    '/dashboard',
    '/start',
    '/finance',
    '/settings',
    '/my-org',
    '/my-org/products',
  ]

  const excludedRoutes = [
    '/api/test',
    '/ingest/test',
    '/docs/overview',
    '/docs/integrate/mcp',
    '/_mintlify/test',
    '/mintlify-assets/test',
    '/_next/static/chunks/test.js',
    '/_next/image',
    '/favicon.ico',
    '/sitemap.xml',
    '/robots.txt',
  ]

  it.each(matchingRoutes)('should match route: %s', (route) => {
    expectMatchesMiddleware(route, true)
  })

  it.each(excludedRoutes)('should NOT match route: %s', (route) => {
    expectMatchesMiddleware(route, false)
  })
})

describe('middleware function', () => {
  let buildServerAPI: ReturnType<typeof vi.fn>

  beforeEach(async () => {
    const clientModule = await import('./utils/client')
    buildServerAPI = clientModule.buildServerAPI as ReturnType<typeof vi.fn>
    vi.clearAllMocks()
  })

  const mockApiResponse = (status: number, data?: unknown) => {
    buildServerAPI.mockResolvedValue({
      GET: vi.fn().mockResolvedValue({
        data,
        response: {
          ok: status >= 200 && status < 300,
          status,
          headers: new Headers(),
        },
      }),
    })
  }

  it('should redirect unauthenticated users from protected routes', async () => {
    const response = await proxy(createRequest('/dashboard'))

    expect(response.status).toBe(307)
    const location = response.headers.get('location')
    expect(location).toContain('/login')
    expect(location).toContain('return_to=%2Fdashboard')
  })

  it('should allow authenticated users to access protected routes', async () => {
    const mockUser = { id: '123', email: 'test@example.com' }
    mockApiResponse(200, mockUser)

    const request = createRequest('/dashboard')
    request.cookies.set('rapidly_session', 'valid-session-token')

    const response = await proxy(request)

    expect(response.status).toBe(200)
    expect(response.headers.get('x-rapidly-user')).toBe(
      JSON.stringify({ id: mockUser.id, avatar_url: undefined }),
    )
  })

  it('should allow unauthenticated access to public routes', async () => {
    const response = await proxy(createRequest('/'))

    expect(response.status).toBe(200)
    expect(response.headers.get('x-rapidly-user')).toBe('')
  })

  it('should redirect to login with query params preserved', async () => {
    const response = await proxy(createRequest('/dashboard?foo=bar&baz=qux'))

    expect(response.status).toBe(307)
    const location = response.headers.get('location')
    expect(location).toContain('/login')
    expect(location).toContain('return_to=%2Fdashboard%3Ffoo%3Dbar%26baz%3Dqux')
  })

  it('should throw error on unexpected API response status', async () => {
    mockApiResponse(500)

    const request = createRequest('/dashboard')
    request.cookies.set('rapidly_session', 'valid-session-token')

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await expect(proxy(request)).rejects.toThrow(
      'Unexpected response status while fetching authenticated user',
    )

    consoleSpy.mockRestore()
  })

  it('should handle 401 responses gracefully', async () => {
    mockApiResponse(401)

    const request = createRequest('/dashboard')
    request.cookies.set('rapidly_session', 'invalid-session-token')

    const response = await proxy(request)

    expect(response.status).toBe(307)
    expect(response.headers.get('location')).toContain('/login')
  })
})

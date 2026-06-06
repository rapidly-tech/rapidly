export interface DocsNavItem {
  title: string
  href: string
}

export interface DocsNavSection {
  title: string
  items: DocsNavItem[]
}

// Hand-maintained navigation tree for the docs sidebar.
// Mirrors the page structure under app/(main)/(website)/docs.
export const docsNav: DocsNavSection[] = [
  {
    title: 'Getting Started',
    items: [
      { title: 'Introduction', href: '/docs' },
      { title: 'Support', href: '/docs/support' },
    ],
  },
  {
    title: 'Features',
    items: [
      { title: 'File Sharing', href: '/docs/features/file-sharing' },
      { title: 'Secret Sharing', href: '/docs/features/secret-sharing' },
      { title: 'Products', href: '/docs/features/products' },
      { title: 'Analytics', href: '/docs/features/analytics' },
      {
        title: 'Customer Management',
        href: '/docs/features/customer-management',
      },
      { title: 'Customer Portal', href: '/docs/features/customer-portal' },
    ],
  },
  {
    title: 'Finance & Payouts',
    items: [
      { title: 'Accounts', href: '/docs/features/finance/accounts' },
      { title: 'Balance', href: '/docs/features/finance/balance' },
      { title: 'Payouts', href: '/docs/features/finance/payouts' },
    ],
  },
  {
    title: 'Integrate',
    items: [
      { title: 'Authentication', href: '/docs/integrate/authentication' },
      { title: 'Workspace Access Tokens', href: '/docs/integrate/oat' },
    ],
  },
  {
    title: 'Webhooks',
    items: [
      { title: 'Endpoints', href: '/docs/integrate/webhooks/endpoints' },
      { title: 'Local Development', href: '/docs/integrate/webhooks/locally' },
      { title: 'Delivery', href: '/docs/integrate/webhooks/delivery' },
      { title: 'Events', href: '/docs/integrate/webhooks/events' },
    ],
  },
  {
    title: 'OAuth 2.0',
    items: [
      { title: 'Introduction', href: '/docs/integrate/oauth2/introduction' },
      { title: 'Setup', href: '/docs/integrate/oauth2/setup' },
      { title: 'Connect', href: '/docs/integrate/oauth2/connect' },
    ],
  },
  {
    title: 'Policies & Fees',
    items: [
      { title: 'Fees', href: '/docs/policies/fees' },
      {
        title: 'Supported Countries',
        href: '/docs/policies/supported-countries',
      },
      { title: 'Acceptable Use', href: '/docs/policies/acceptable-use' },
      { title: 'Account Reviews', href: '/docs/policies/account-reviews' },
    ],
  },
  {
    title: 'Guides',
    items: [
      { title: 'Overview', href: '/docs/guides/introduction' },
      {
        title: 'Change Email as Merchant',
        href: '/docs/guides/change-email-as-merchant',
      },
      {
        title: 'Multiple Workspaces',
        href: '/docs/guides/create-multiple-organizations',
      },
    ],
  },
  {
    title: 'API Reference',
    items: [
      { title: 'Introduction', href: '/docs/api-reference/introduction' },
    ],
  },
  {
    title: 'Changelog',
    items: [
      { title: 'Recent Changes', href: '/docs/changelog/recent' },
      { title: 'API Changelog', href: '/docs/changelog/api' },
    ],
  },
]

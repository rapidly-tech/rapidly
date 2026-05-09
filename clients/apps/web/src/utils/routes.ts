/** Centralized route path constants to avoid hardcoded strings throughout the app */

export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  VERIFY_EMAIL: '/verify-email',
  START: '/start',

  DASHBOARD: {
    ROOT: '/dashboard',
    ACCOUNT: '/dashboard/account',
    ACCOUNT_PREFERENCES: '/dashboard/account/preferences',
    org: (slug: string) => `/dashboard/${slug}`,
    files: {
      new: (slug: string) => `/dashboard/${slug}/shares/send-files`,
    },
    settings: (slug: string) => `/dashboard/${slug}/settings`,
    settingsDevelopers: (slug: string) =>
      `/dashboard/${slug}/settings#developers`,
    finance: {
      account: (slug: string) => `/dashboard/${slug}/finance/account`,
    },
  },

  PORTAL: {
    root: (slug: string) => `/${slug}/portal`,
    request: (slug: string) => `/${slug}/portal/request`,
    settings: (slug: string) => `/${slug}/portal/settings`,
  },
} as const

'use client'

import { RapidlyLogotype } from '@/components/Layout/Public/RapidlyLogotype'
import Footer from '@/components/Workspace/Footer'
import { CONFIG } from '@/utils/config'
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from '@rapidly-tech/ui/components/navigation/Sidebar'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { ComponentProps, PropsWithChildren } from 'react'
import { twMerge } from 'tailwind-merge'
import { NavPopover, NavPopoverSection } from './NavPopover'

// ── Main Layout ──

export default function Layout({ children }: PropsWithChildren) {
  return (
    <div className="rp-page-bg relative flex min-h-dvh flex-col overflow-hidden px-0 md:w-full md:items-center md:px-4">
      <a
        href="#main-content"
        className="focus:rp-text-primary sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-md focus:bg-(--surface-inset) focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:shadow-lg focus:outline-none"
      >
        Skip to main content
      </a>
      <LandingPageDesktopNavigation />
      <SidebarProvider className="absolute inset-0 flex flex-col items-start md:hidden">
        <LandingPageTopbar />
        <LandingPageMobileNavigation />
      </SidebarProvider>

      <main
        id="main-content"
        className="relative flex w-full flex-1 flex-col px-4 pt-32 md:w-full md:px-0 md:pt-0"
      >
        {children}
      </main>
      <Footer />
    </div>
  )
}

// ── NavLink Component ──

const NavLink = ({
  href,
  className,
  children,
  isActive: _isActive,
  target,
  ...props
}: ComponentProps<typeof Link> & {
  isActive?: (pathname: string) => boolean
}) => {
  const pathname = usePathname()
  const isActive = _isActive
    ? _isActive(pathname)
    : pathname.startsWith(href.toString())
  const isExternal = href.toString().startsWith('http')

  return (
    <Link
      href={href}
      target={isExternal ? '_blank' : target}
      prefetch
      className={twMerge(
        'rp-text-secondary hover:rp-text-primary -m-1 flex items-center gap-x-2 p-1 transition-colors',
        isActive && 'rp-text-primary',
        className,
      )}
      {...props}
    >
      {children}
    </Link>
  )
}

// ── Navigation Data ──

interface NavigationItem {
  title: string
  href: string
  isActive?: (pathname: string) => boolean
  target?: '_blank'
}

const mobileFeatureItems: NavigationItem[] = [
  { title: 'Secure Sharing', href: '/features/shares' },
  { title: 'Secret Messages', href: '/features/secret-messages' },
  { title: 'Payments', href: '/features/payments' },
  { title: 'Finance', href: '/features/finance' },
]

const mobileDocsItems: NavigationItem[] = [
  {
    title: 'Documentation Portal',
    href: CONFIG.DOCS_BASE_URL,
    target: '_blank',
  },
  {
    title: 'File Sharing',
    href: `${CONFIG.DOCS_BASE_URL}/features/file-sharing`,
    target: '_blank',
  },
  {
    title: 'Secret Messages',
    href: `${CONFIG.DOCS_BASE_URL}/features/secret-sharing`,
    target: '_blank',
  },
  {
    title: 'Payments',
    href: `${CONFIG.DOCS_BASE_URL}/features/products`,
    target: '_blank',
  },
]

const mobileNavigationItems: NavigationItem[] = [
  {
    title: 'About',
    href: '/about',
  },
]

// ── Mobile Navigation ──

const LandingPageMobileNavigation = () => {
  const sidebar = useSidebar()

  return (
    <>
      <Sidebar className="md:hidden">
        <SidebarHeader className="p-4">
          <RapidlyLogotype logoVariant="icon" href="/" />
        </SidebarHeader>
        <SidebarContent className="flex flex-col gap-y-6 px-6 py-2">
          <nav aria-label="Mobile navigation" className="flex flex-col gap-y-1">
            <span className="rp-text-muted text-sm font-medium tracking-wider uppercase">
              Features
            </span>
            {mobileFeatureItems.map((item) => (
              <NavLink
                key={item.title}
                className="pl-2 text-lg tracking-tight"
                href={item.href}
                onClick={sidebar.toggleSidebar}
              >
                {item.title}
              </NavLink>
            ))}
            <div className="my-2" />
            <span className="rp-text-muted text-sm font-medium tracking-wider uppercase">
              Docs
            </span>
            {mobileDocsItems.map((item) => (
              <NavLink
                key={item.title}
                className="pl-2 text-lg tracking-tight"
                href={item.href}
                target={item.target}
                onClick={sidebar.toggleSidebar}
              >
                {item.title}
              </NavLink>
            ))}
            <div className="my-2" />
            {mobileNavigationItems.map((item) => (
              <NavLink
                key={item.title}
                className="text-xl tracking-tight"
                isActive={item.isActive}
                target={item.target}
                href={item.href}
                onClick={sidebar.toggleSidebar}
              >
                {item.title}
              </NavLink>
            ))}
          </nav>
          <Link
            href="/login"
            className="rp-text-secondary hover:rp-text-primary -m-1 flex items-center gap-x-2 p-1 text-xl tracking-tight transition-colors"
          >
            Login
          </Link>
        </SidebarContent>
      </Sidebar>
    </>
  )
}

// ── Desktop Navigation ──

const LandingPageDesktopNavigation = () => {
  const pathname = usePathname()

  const featuresSections: NavPopoverSection[] = [
    {
      items: [
        {
          href: '/features/shares',
          label: 'Secure Sharing',
          subtitle: 'Encrypted file transfers',
        },
        {
          href: '/features/secret-messages',
          label: 'Secret Messages',
          subtitle: 'Encrypted text sharing',
        },
        {
          href: '/features/payments',
          label: 'Payments',
          subtitle: 'Accept payments for shares',
        },
        {
          href: '/features/finance',
          label: 'Finance',
          subtitle: 'Payouts & Reporting',
        },
      ],
    },
  ]

  const docsSections: NavPopoverSection[] = [
    {
      title: 'Getting Started',
      items: [
        {
          href: CONFIG.DOCS_BASE_URL,
          label: 'Documentation Portal',
          target: '_blank',
          subtitle: 'Get started with Rapidly',
        },
        {
          href: `${CONFIG.DOCS_BASE_URL}/features/file-sharing`,
          label: 'File Sharing',
          target: '_blank',
          subtitle: 'Send files securely',
        },
        {
          href: `${CONFIG.DOCS_BASE_URL}/features/secret-sharing`,
          label: 'Secret Messages',
          target: '_blank',
          subtitle: 'Encrypted text sharing',
        },
      ],
    },
    {
      title: 'Advanced',
      items: [
        {
          href: `${CONFIG.DOCS_BASE_URL}/features/products`,
          label: 'Payments',
          target: '_blank',
          subtitle: 'Accept payments for files',
        },
        {
          href: `${CONFIG.DOCS_BASE_URL}/features/finance/payouts`,
          label: 'Finance & Payouts',
          subtitle: 'Detailed financial insights',
          target: '_blank',
        },
      ],
    },
  ]

  return (
    <nav
      aria-label="Main navigation"
      className="rp-text-primary relative z-20 hidden w-full flex-col items-center gap-12 py-8 md:flex"
    >
      <div className="relative flex w-full flex-row items-center justify-between lg:max-w-6xl">
        <RapidlyLogotype logoVariant="icon" size={40} href="/" />

        <ul className="absolute left-1/2 mx-auto flex -translate-x-1/2 flex-row gap-x-8 font-medium">
          <li>
            <NavPopover
              trigger="Features"
              sections={featuresSections}
              isActive={pathname.startsWith('/features')}
            />
          </li>
          <li>
            <NavPopover trigger="Docs" sections={docsSections} layout="flex" />
          </li>
          <li>
            <NavLink href="/about">About</NavLink>
          </li>
        </ul>

        <Link
          href="/login"
          className="rounded-full bg-(--surface-bold) px-4 py-2 text-sm font-medium text-(--text-inverted) transition-colors hover:bg-(--surface-bold-hover)"
        >
          Paid Share
        </Link>
      </div>
    </nav>
  )
}

// ── Mobile Topbar ──

const LandingPageTopbar = () => {
  return (
    <div className="z-30 flex w-full flex-row items-center justify-between px-6 py-6 md:hidden md:px-12">
      <RapidlyLogotype
        className="mt-1 ml-2 md:hidden"
        logoVariant="icon"
        size={32}
        href="/"
      />
      <SidebarTrigger className="md:hidden" aria-label="Open navigation menu" />
    </div>
  )
}

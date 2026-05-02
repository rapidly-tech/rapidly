import { CONFIG } from '@/utils/config'
import Link from 'next/link'

const Footer = () => {
  return (
    <footer className="mt-auto flex w-full flex-col items-center px-6 pt-4 pb-6">
      <div className="flex w-full max-w-2xl flex-row items-center justify-center gap-4 text-xs">
        <span
          className="whitespace-nowrap text-slate-500 dark:text-slate-500"
          suppressHydrationWarning
        >
          &copy; {new Date().getFullYear()} Rapidly
        </span>
        <Link
          href={CONFIG.LEGAL_TERMS_URL}
          target="_blank"
          className="whitespace-nowrap text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300"
        >
          Terms &amp; Conditions
        </Link>
        <Link
          href={CONFIG.LEGAL_PRIVACY_URL}
          target="_blank"
          className="whitespace-nowrap text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300"
        >
          Privacy Policy
        </Link>
        <Link
          href="https://status.rapidly.tech"
          target="_blank"
          className="whitespace-nowrap text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300"
        >
          Status
        </Link>
      </div>
    </footer>
  )
}

export default Footer

import { CONFIG } from '@/utils/config'
import Link from 'next/link'

const Footer = () => {
  return (
    <footer className="mt-auto flex w-full flex-col items-center px-6 pt-16 pb-6">
      <div className="flex w-full max-w-2xl flex-row items-center justify-center gap-4 text-xs">
        <span
          className="whitespace-nowrap text-slate-400 dark:text-slate-700"
          suppressHydrationWarning
        >
          &copy; {new Date().getFullYear()} Rapidly
        </span>
        <Link
          href={CONFIG.LEGAL_TERMS_URL}
          target="_blank"
          className="whitespace-nowrap text-slate-400 transition-colors hover:text-slate-600 dark:text-slate-700 dark:hover:text-slate-400"
        >
          Terms &amp; Conditions
        </Link>
        <Link
          href={CONFIG.LEGAL_PRIVACY_URL}
          target="_blank"
          className="whitespace-nowrap text-slate-400 transition-colors hover:text-slate-600 dark:text-slate-700 dark:hover:text-slate-400"
        >
          Privacy Policy
        </Link>
        <Link
          href="https://status.rapidly.tech"
          target="_blank"
          className="whitespace-nowrap text-slate-400 transition-colors hover:text-slate-600 dark:text-slate-700 dark:hover:text-slate-400"
        >
          Status
        </Link>
      </div>
    </footer>
  )
}

export default Footer

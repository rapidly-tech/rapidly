import { CONFIG } from '@/utils/config'
import Link from 'next/link'

const Footer = () => {
  return (
    <footer className="sticky bottom-0 z-10 mt-auto flex w-full flex-col items-center bg-(--background)/85 px-6 pt-4 pb-6 backdrop-blur-md">
      <div className="flex w-full max-w-2xl flex-row items-center justify-center gap-4 text-xs">
        <span
          className="whitespace-nowrap text-slate-700 dark:text-slate-400"
          suppressHydrationWarning
        >
          &copy; {new Date().getFullYear()} Rapidly
        </span>
        <Link
          href={CONFIG.LEGAL_TERMS_URL}
          target="_blank"
          className="whitespace-nowrap text-slate-700 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
        >
          Terms &amp; Conditions
        </Link>
        <Link
          href={CONFIG.LEGAL_PRIVACY_URL}
          target="_blank"
          className="whitespace-nowrap text-slate-700 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
        >
          Privacy Policy
        </Link>
        <Link
          href="https://status.rapidly.tech"
          target="_blank"
          className="whitespace-nowrap text-slate-700 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
        >
          Status
        </Link>
      </div>
    </footer>
  )
}

export default Footer

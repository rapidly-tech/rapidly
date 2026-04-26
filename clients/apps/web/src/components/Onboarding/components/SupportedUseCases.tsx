import { CONFIG } from '@/utils/config'

export default function SupportedUseCases() {
  return (
    <div className="flex flex-col gap-y-4 text-sm">
      <div className="flex flex-col gap-y-2">
        <p className="font-medium">Supported Usecases</p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Secure peer-to-peer file sharing, encrypted file transfers, digital
          downloads, and file access management for teams and customers.
        </p>
      </div>

      <div className="flex flex-col gap-y-2">
        <p className="font-medium">Prohibited Usecases</p>
        <ul className="space-y-1 text-sm text-slate-500 dark:text-slate-400">
          <li>• Sharing copyrighted content without authorization</li>
          <li>• Distribution of malware or harmful software</li>
          <li>• Illegal content or materials violating applicable laws</li>
          <li>
            • Anything in our list of{' '}
            <a
              href={`${CONFIG.DOCS_BASE_URL}/acceptable-use`}
              className="text-slate-600 underline dark:text-slate-400"
              target="_blank"
              rel="noreferrer"
            >
              prohibited content
            </a>
          </li>
        </ul>
      </div>

      <div className="border-t border-slate-200 pt-4 dark:border-slate-800">
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Files that violate our policy will be removed and accounts may be
          suspended.
        </p>
      </div>
    </div>
  )
}

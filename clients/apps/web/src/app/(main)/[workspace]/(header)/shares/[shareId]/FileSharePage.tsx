import { formatFileSize } from '@/utils/file-sharing/constants'
import { StorefrontFileShare } from '@/utils/storefront'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'

const FileSharePage = ({
  workspace,
  fileShare,
}: {
  workspace: schemas['CustomerWorkspace']
  fileShare: StorefrontFileShare
}) => {
  const title = fileShare.title || fileShare.file_name || 'Shared File'
  const fileSizeFormatted = fileShare.file_size_bytes
    ? formatFileSize(fileShare.file_size_bytes)
    : null

  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <div className="flex w-full max-w-md flex-col gap-6 rounded-2xl border border-slate-200 bg-white p-8 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col gap-2">
          <h1 className="rp-text-primary text-2xl font-semibold">{title}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Shared by {workspace.name}
          </p>
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-200 pt-4 dark:border-slate-800">
          {fileSizeFormatted && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500 dark:text-slate-400">
                File size
              </span>
              <span className="text-sm font-medium dark:text-slate-200">
                {fileSizeFormatted}
              </span>
            </div>
          )}
          {fileShare.price_cents != null && fileShare.price_cents > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500 dark:text-slate-400">
                Price
              </span>
              <span className="rp-text-primary text-lg font-semibold">
                ${(fileShare.price_cents / 100).toFixed(2)}{' '}
                {fileShare.currency.toUpperCase()}
              </span>
            </div>
          )}
        </div>

        <Link href={`/download/${fileShare.short_slug}`}>
          <Button className="w-full" size="lg">
            {fileShare.price_cents != null && fileShare.price_cents > 0
              ? `Buy & Download — $${(fileShare.price_cents / 100).toFixed(2)}`
              : 'Download File'}
          </Button>
        </Link>
      </div>
    </div>
  )
}

export default FileSharePage

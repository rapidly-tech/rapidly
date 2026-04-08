'use client'

import { formatFileSize } from '@/utils/file-sharing/constants'
import { StorefrontFileShare, StorefrontSecret } from '@/utils/storefront'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import Link from 'next/link'

/** Renders a grid of file share and secret cards for an workspace's storefront page. */
export const Storefront = ({
  workspace,
  fileShares,
  secrets = [],
}: {
  workspace: schemas['CustomerWorkspace']
  fileShares: StorefrontFileShare[]
  secrets?: StorefrontSecret[]
}) => {
  const hasContent = fileShares.length > 0 || secrets.length > 0

  return (
    <div className="flex w-full flex-col gap-y-8">
      {hasContent ? (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {fileShares.map((file) => (
            <div
              key={file.id}
              className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="flex flex-col gap-2">
                <h3 className="rp-text-primary text-lg font-medium">
                  {file.title || file.file_name || 'Untitled File'}
                </h3>
                {file.file_size_bytes && (
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    {formatFileSize(file.file_size_bytes)}
                  </p>
                )}
              </div>
              <div className="mt-auto flex items-center justify-between">
                {file.price_cents != null && file.price_cents > 0 && (
                  <span className="rp-text-primary text-lg font-medium">
                    ${(file.price_cents / 100).toFixed(2)}
                  </span>
                )}
                <Link href={`/${workspace.slug}/shares/${file.short_slug}`}>
                  <Button size="sm">Get File</Button>
                </Link>
              </div>
            </div>
          ))}
          {secrets.map((secret) => (
            <div
              key={secret.id}
              className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <Icon
                    icon="solar:lock-linear"
                    className="h-4 w-4 text-slate-400 dark:text-slate-500"
                  />
                  <span className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
                    Secret
                  </span>
                </div>
                <h3 className="rp-text-primary text-lg font-medium">
                  {secret.title || 'Encrypted Secret'}
                </h3>
              </div>
              <div className="mt-auto flex items-center justify-between">
                {secret.price_cents != null && secret.price_cents > 0 && (
                  <span className="rp-text-primary text-lg font-medium">
                    ${(secret.price_cents / 100).toFixed(2)}
                  </span>
                )}
                <Link href={`/${workspace.slug}/secrets/${secret.uuid}`}>
                  <Button size="sm">View Secret</Button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex w-full flex-col items-center justify-center py-24">
          <p className="text-slate-500 dark:text-slate-400">
            No items available
          </p>
        </div>
      )}
    </div>
  )
}

import LogoType from '@/components/Brand/LogoType'
import { Icon } from '@iconify/react'
import { schemas } from '@rapidly-tech/client'
import Link from 'next/link'

export default function SharedLayout({
  client,
  introduction,
  children,
}: {
  client?: schemas['AuthorizeResponseWorkspace']['client']
  introduction?: string | React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <div className="rp-page-bg flex min-h-dvh flex-col gap-12 pt-16 md:items-center md:p-16">
      <div className="flex w-96 flex-col items-center gap-6">
        <div className="flex flex-row items-center gap-2">
          <Link href="/">
            <LogoType className="h-10" />
          </Link>
          {client?.logo_uri && (
            <>
              <Icon icon="solar:add-circle-linear" className="h-5 w-5" />
              {/* eslint-disable-next-line @next/next/no-img-element, no-restricted-syntax */}
              <img
                src={client.logo_uri}
                className="h-10"
                alt={client.client_name ?? client.client_id}
              />
            </>
          )}
        </div>
        {introduction && (
          <div className="w-full text-center text-lg text-slate-600 dark:text-slate-400">
            {introduction}
          </div>
        )}
      </div>
      {children && <div className="flex w-lg flex-col gap-6">{children}</div>}
    </div>
  )
}

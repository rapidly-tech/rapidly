'use client'

// ── Imports ──

import { DashboardBody } from '@/components/Layout/DashboardLayout'
import MetricChartBox from '@/components/Metrics/MetricChartBox'
import { IOSAppBanner } from '@/components/Upsell/IOSAppBanner'
import { AccountWidget } from '@/components/Widgets/AccountWidget'
import { FileShareActivityWidget } from '@/components/Widgets/FileShareActivityWidget'
import FileShareRevenueWidget from '@/components/Widgets/FileShareRevenueWidget'
import { FilesWidget } from '@/components/Widgets/FilesWidget'
import { RecentFilesWidget } from '@/components/Widgets/RecentFilesWidget'
import { useMetrics, useWorkspacePaymentStatus } from '@/hooks/api'
import { useFileShareSessions } from '@/hooks/api/fileShareSessions'
import {
  ALL_METRICS,
  getChartRangeParams,
  getPreviousParams,
} from '@/utils/metrics'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { useMemo, useState } from 'react'
import { twMerge } from 'tailwind-merge'

// ── Types ──

interface HeroChartProps {
  workspace: schemas['Workspace']
}

// ── Sub-Components ──

const HeroChart = ({ workspace }: HeroChartProps) => {
  const [selectedMetric, setSelectedMetric] = useState<
    keyof schemas['Metrics']
  >('file_share_sessions' as keyof schemas['Metrics'])
  const [startDate, endDate, interval] = useMemo(
    () => getChartRangeParams('30d', workspace.created_at),
    [workspace.created_at],
  )

  const { data: currentPeriodData, isLoading: currentPeriodLoading } =
    useMetrics({
      workspace_id: workspace.id,
      startDate: startDate,
      endDate: endDate,
      interval: interval,
      metrics: [selectedMetric],
    })

  const previousParams = useMemo(
    () => getPreviousParams(startDate, '30d'),
    [startDate],
  )

  const { data: previousPeriodData, isLoading: previousPeriodLoading } =
    useMetrics(
      {
        workspace_id: workspace.id,
        startDate: previousParams ? previousParams[0] : startDate,
        endDate: previousParams ? previousParams[1] : endDate,
        interval: interval,
        metrics: [selectedMetric],
      },
      previousParams !== null,
    )

  return (
    <MetricChartBox
      metric={selectedMetric}
      onMetricChange={setSelectedMetric}
      data={currentPeriodData}
      previousData={previousPeriodData}
      interval={interval}
      loading={currentPeriodLoading || previousPeriodLoading}
      chartType="line"
      availableMetrics={ALL_METRICS}
    />
  )
}

interface OverviewPageProps {
  workspace: schemas['Workspace']
}

// ── Main Component ──

export default function OverviewPage({ workspace }: OverviewPageProps) {
  const { data: paymentStatus } = useWorkspacePaymentStatus(
    workspace.id,
    true,
    true,
  )

  const { data: sessionsData } = useFileShareSessions({
    workspace_id: workspace.id,
    limit: 1,
  })
  const hasNoSessions = sessionsData && sessionsData.data.length === 0

  const motionVariants = {
    variants: {
      initial: { opacity: 0 },
      animate: { opacity: 1, transition: { duration: 0.3 } },
      exit: { opacity: 0, transition: { duration: 0.3 } },
    },
  }
  const cardClassName = 'flex w-full flex-col h-full'

  return (
    <DashboardBody className="gap-y-8 pb-16 md:gap-y-12">
      <IOSAppBanner />
      {paymentStatus && !paymentStatus.payment_ready && (
        <Link
          href={`/dashboard/${workspace.slug}/finance/account`}
          className="glass-elevated flex items-center justify-between rounded-2xl bg-slate-50 px-5 py-4 shadow-xs transition-colors lg:rounded-3xl dark:bg-slate-900"
        >
          <div className="flex flex-col gap-y-0.5">
            <p className="rp-text-primary text-sm font-medium">
              Connect Stripe to accept payments for file shares
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Set up your Stripe account to start accepting paid file transfers
            </p>
          </div>
          <Button size="sm" variant="secondary">
            Connect Stripe
          </Button>
        </Link>
      )}
      {hasNoSessions && (
        <div className="glass-elevated flex flex-col gap-6 rounded-2xl bg-slate-50 p-6 shadow-xs lg:rounded-3xl dark:bg-slate-900">
          <div>
            <h2 className="rp-text-primary text-xl font-medium">
              Getting Started
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Welcome! Here&apos;s how to get started with Rapidly.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Link
              href={`/dashboard/${workspace.slug}/settings`}
              className="flex flex-col gap-2 rounded-xl bg-white p-4 transition-colors hover:bg-slate-100 dark:bg-slate-950 dark:hover:bg-slate-800"
            >
              <span className="rp-text-primary text-sm font-medium">
                1. Customize your page
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Set up your public page and workspace settings
              </span>
            </Link>
            <Link
              href={`/dashboard/${workspace.slug}/finance/account`}
              className="flex flex-col gap-2 rounded-xl bg-white p-4 transition-colors hover:bg-slate-100 dark:bg-slate-950 dark:hover:bg-slate-800"
            >
              <span className="rp-text-primary text-sm font-medium">
                2. Set up paid sharing
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Connect Stripe to accept payments for file transfers
              </span>
            </Link>
            <Link
              href={`/dashboard/${workspace.slug}/shares/send-files`}
              className="flex flex-col gap-2 rounded-xl bg-white p-4 transition-colors hover:bg-slate-100 dark:bg-slate-950 dark:hover:bg-slate-800"
            >
              <span className="rp-text-primary text-sm font-medium">
                3. Send your first file
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Share files securely with anyone via P2P transfer
              </span>
            </Link>
          </div>
        </div>
      )}
      <HeroChart workspace={workspace} />
      <motion.div
        className="grid grid-cols-1 gap-6 md:gap-10 xl:grid-cols-3"
        initial="initial"
        animate="animate"
        exit="exit"
        transition={{ staggerChildren: 0.1 }}
      >
        <motion.div className={cardClassName} {...motionVariants}>
          <FileShareActivityWidget />
        </motion.div>
        <motion.div
          className={twMerge(cardClassName, 'xl:col-span-2')}
          {...motionVariants}
        >
          <FileShareRevenueWidget />
        </motion.div>
        <motion.div className={cardClassName} {...motionVariants}>
          <RecentFilesWidget />
        </motion.div>
        <motion.div className={cardClassName} {...motionVariants}>
          <FilesWidget />
        </motion.div>
        <motion.div className={cardClassName} {...motionVariants}>
          <AccountWidget />
        </motion.div>
      </motion.div>
    </DashboardBody>
  )
}

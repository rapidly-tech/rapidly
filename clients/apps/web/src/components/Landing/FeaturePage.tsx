'use client'

import { Icon } from '@iconify/react'
import { motion, type Variants } from 'framer-motion'
import Link from 'next/link'
import { useMemo } from 'react'

// ── Icon Registry ──

const iconMap: Record<string, string> = {
  Lock: 'solar:lock-linear',
  ArrowLeftRight: 'solar:transfer-horizontal-linear',
  Infinity: 'solar:infinity-linear',
  ShieldCheck: 'solar:shield-check-linear',
  Cloud: 'solar:cloud-linear',
  Eye: 'solar:eye-linear',
  Trash2: 'solar:trash-bin-trash-linear',
  CreditCard: 'solar:card-linear',
  Zap: 'solar:bolt-linear',
  Globe: 'solar:global-linear',
  BarChart3: 'solar:chart-2-linear',
  Banknote: 'solar:dollar-minimalistic-linear',
  TrendingUp: 'solar:graph-up-linear',
  FileText: 'solar:document-text-linear',
  GitHub: 'mdi:github',
  Monitor: 'solar:monitor-linear',
  Users: 'solar:users-group-rounded-linear',
  Wifi: 'solar:wi-fi-router-linear',
}

// ── Animation ──

const STAGGER_DELAY = 0.12
const FADE_DURATION = 0.8

const buildContainerVariants = (stagger: number): Variants => ({
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: stagger },
  },
})

const buildItemVariants = (duration: number): Variants => ({
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration } },
})

// ── Types ──

export interface FeatureCard {
  icon: string
  title: string
  description: string
  href?: string
}

export interface FeaturePageProps {
  description?: string
  features: FeatureCard[]
  ctaLabel: string
  ctaHref: string
  docsHref: string
}

// ── Component ──

export const FeaturePage = ({
  description,
  features,
  ctaLabel,
  ctaHref,
  docsHref,
}: FeaturePageProps) => {
  const containerVariants = useMemo(
    () => buildContainerVariants(STAGGER_DELAY),
    [],
  )
  const itemVariants = useMemo(() => buildItemVariants(FADE_DURATION), [])

  return (
    <div className="relative flex w-full max-w-full flex-col items-center overflow-x-hidden px-4">
      {/* Description Card — full width */}
      {description && (
        <motion.div
          className="relative z-10 mx-auto w-full max-w-4xl pt-6 md:pt-12"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
        >
          <motion.div
            className="glass-elevated rounded-2xl bg-slate-50 p-7 text-center shadow-xs transition-transform hover:scale-[1.02] dark:bg-slate-900"
            variants={itemVariants}
          >
            <p className="rp-text-primary text-lg leading-relaxed font-medium text-balance whitespace-pre-line md:text-xl">
              {description}
            </p>
          </motion.div>
        </motion.div>
      )}

      {/* Feature Cards — 2×2 grid */}
      <motion.div
        className={`relative z-10 mx-auto grid w-full max-w-4xl gap-5 pt-5 ${features.length === 1 ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-2'}`}
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true }}
      >
        {features.map((feature) => {
          const iconName = iconMap[feature.icon]
          return (
            <motion.div
              key={feature.title}
              className={`glass-elevated flex flex-col gap-4 rounded-2xl bg-slate-50 p-7 shadow-xs transition-transform hover:scale-[1.02] dark:bg-slate-900 ${feature.href ? 'cursor-pointer' : ''}`}
              variants={itemVariants}
              onClick={
                feature.href
                  ? () => window.open(feature.href, '_blank')
                  : undefined
              }
            >
              <div className="flex items-center gap-3">
                {iconName && (
                  <Icon
                    icon={iconName}
                    className="rp-text-secondary h-5 w-5 shrink-0"
                  />
                )}
                <h3 className="text-lg font-semibold">{feature.title}</h3>
              </div>
              <p className="rp-text-secondary text-sm leading-relaxed whitespace-pre-line">
                {feature.description}
              </p>
            </motion.div>
          )
        })}
      </motion.div>

      {/* CTAs */}
      <motion.div
        className="relative z-10 mt-8 flex flex-col items-center gap-4 pb-12 md:flex-row md:gap-6"
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true }}
      >
        <motion.div variants={itemVariants}>
          <Link
            href={ctaHref}
            className="inline-flex items-center rounded-full bg-(--surface-bold) px-6 py-3 text-sm font-medium text-(--text-inverted) transition-colors hover:bg-(--surface-bold-hover)"
          >
            {ctaLabel}
          </Link>
        </motion.div>
        <motion.div variants={itemVariants}>
          <Link
            href={docsHref}
            className="rp-text-secondary hover:rp-text-primary text-sm font-medium transition-colors"
          >
            Read the docs
          </Link>
        </motion.div>
      </motion.div>
    </div>
  )
}

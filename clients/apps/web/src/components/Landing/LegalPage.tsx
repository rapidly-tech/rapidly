'use client'

import { Icon } from '@iconify/react'
import { motion, type Variants } from 'framer-motion'
import DOMPurify from 'isomorphic-dompurify'
import { useMemo } from 'react'

// ── Icon Registry ──

const iconMap: Record<string, string> = {
  FileText: 'solar:document-text-linear',
  Shield: 'solar:shield-linear',
  Scale: 'solar:scale-linear',
}

// ── Animation ──

const STAGGER_DELAY = 0.1
const FADE_DURATION = 0.7

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

export interface LegalSection {
  title: string
  content: string
}

export interface LegalPageProps {
  icon?: string
  title: string
  effectiveDate: string
  intro: string
  sections: LegalSection[]
}

// ── Component ──

export const LegalPage = ({
  icon = 'FileText',
  title,
  effectiveDate,
  intro,
  sections,
}: LegalPageProps) => {
  const containerVariants = useMemo(
    () => buildContainerVariants(STAGGER_DELAY),
    [],
  )
  const itemVariants = useMemo(() => buildItemVariants(FADE_DURATION), [])
  const iconName = iconMap[icon]

  return (
    <div className="relative flex flex-1 flex-col items-center px-4">
      {/* Header */}
      <motion.div
        className="relative z-10 mx-auto w-full max-w-4xl pt-6 md:pt-12"
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true }}
      >
        <motion.div
          className="glass-elevated rounded-2xl bg-slate-50 p-7 text-center shadow-xs dark:bg-slate-900"
          variants={itemVariants}
        >
          <div className="mb-4 flex items-center justify-center gap-3">
            {iconName && (
              <Icon
                icon={iconName}
                className="rp-text-secondary h-6 w-6 shrink-0"
              />
            )}
            <h1 className="text-2xl font-bold md:text-3xl">{title}</h1>
          </div>
          <p className="rp-text-secondary text-sm">
            Effective date: {effectiveDate}
          </p>
        </motion.div>
      </motion.div>

      {/* Intro */}
      <motion.div
        className="relative z-10 mx-auto w-full max-w-4xl pt-5"
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true }}
      >
        <motion.div
          className="glass-elevated rounded-2xl bg-slate-50 p-7 shadow-xs dark:bg-slate-900"
          variants={itemVariants}
        >
          <p className="rp-text-primary text-sm leading-relaxed md:text-base">
            {intro}
          </p>
        </motion.div>
      </motion.div>

      {/* Sections */}
      <motion.div
        className="relative z-10 mx-auto flex w-full max-w-4xl flex-col gap-5 pt-5 pb-16"
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true }}
      >
        {sections.map((section) => (
          <motion.div
            key={section.title}
            className="glass-elevated rounded-2xl bg-slate-50 p-7 shadow-xs dark:bg-slate-900"
            variants={itemVariants}
          >
            <h2 className="mb-4 text-lg font-semibold">{section.title}</h2>
            <div
              className="rp-text-secondary prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed"
              dangerouslySetInnerHTML={{
                __html: DOMPurify.sanitize(section.content),
              }}
            />
          </motion.div>
        ))}
      </motion.div>
    </div>
  )
}

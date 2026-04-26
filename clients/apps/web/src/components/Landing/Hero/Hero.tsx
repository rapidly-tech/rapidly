'use client'

import { motion, type Variants } from 'framer-motion'
import { PropsWithChildren, useMemo } from 'react'
import { twMerge } from 'tailwind-merge'

const STAGGER_DELAY = 0.1
const FADE_DURATION = 1

const buildContainerVariants = (stagger: number): Variants => ({
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: stagger },
  },
})

const buildItemVariants = (duration: number): Variants => ({
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration } },
})

const BASE_WRAPPER_CLASSES =
  'relative flex flex-col items-center justify-center gap-4 px-4 pt-8 text-center md:pt-12'

const HEADING_CLASSES =
  'text-5xl leading-tight! tracking-tight text-balance md:px-0 md:text-7xl'

const DESCRIPTION_CLASSES =
  'rp-text-secondary max-w-2xl text-center text-2xl leading-relaxed! text-balance'

const ACTIONS_CLASSES =
  'mt-6 flex flex-col items-center gap-4 md:flex-row md:gap-6'

export type HeroProps = PropsWithChildren<{
  className?: string
  title: string
  description: string
}>

export const Hero = ({
  className,
  title,
  description,
  children,
}: HeroProps) => {
  const containerVariants = useMemo(
    () => buildContainerVariants(STAGGER_DELAY),
    [],
  )
  const itemVariants = useMemo(() => buildItemVariants(FADE_DURATION), [])

  const wrapperClassName = useMemo(
    () => twMerge(BASE_WRAPPER_CLASSES, className),
    [className],
  )

  return (
    <motion.div
      className={wrapperClassName}
      variants={containerVariants}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true }}
    >
      <HeroTitle variants={itemVariants}>{title}</HeroTitle>
      <HeroDescription variants={itemVariants}>{description}</HeroDescription>
      <motion.div className={ACTIONS_CLASSES} variants={itemVariants}>
        {children}
      </motion.div>
    </motion.div>
  )
}

const HeroTitle = ({
  children,
  variants,
}: {
  children: React.ReactNode
  variants: Variants
}) => (
  <motion.h1 className={HEADING_CLASSES} variants={variants}>
    {children}
  </motion.h1>
)

const HeroDescription = ({
  children,
  variants,
}: {
  children: React.ReactNode
  variants: Variants
}) => (
  <motion.p className={DESCRIPTION_CLASSES} variants={variants}>
    {children}
  </motion.p>
)

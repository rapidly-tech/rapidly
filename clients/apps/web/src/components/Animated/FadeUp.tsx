import { HTMLMotionProps, motion, type Variants } from 'framer-motion'

export type FadeUpProps = HTMLMotionProps<'div'>

const DEFAULT_TRANSLATE_Y = 10
const DEFAULT_DURATION = 1

const createFadeUpVariants = (
  translateY: number = DEFAULT_TRANSLATE_Y,
  duration: number = DEFAULT_DURATION,
): Variants => ({
  hidden: { opacity: 0, y: translateY },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration },
  },
})

const defaultVariants = createFadeUpVariants()

export const FadeUp = ({
  variants = defaultVariants,
  ...props
}: Omit<HTMLMotionProps<'div'>, 'children' | 'variants'> & FadeUpProps) => (
  <motion.div variants={variants} {...props} />
)

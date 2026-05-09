import ProseWrapper from '@/components/MDX/ProseWrapper'
import type { MDXComponents } from 'mdx/types'
// eslint-disable-next-line no-restricted-imports
import Image from 'next/image'
import { twMerge } from 'tailwind-merge'

interface ImportedImageSrc {
  src: string
  height: number
  width: number
  blurDataURL: string
  blurWidth: number
  blurHeight: number
}

const BODY_WRAPPER_CLASSES = 'flex w-full flex-col items-center md:max-w-7xl!'

const HEADER_WRAPPER_CLASSES =
  'prose-headings:font-normal prose-h1:leading-tight prose-headings:text-balance pt-6 text-center md:max-w-3xl md:pt-0 md:pb-6'

const INNER_WRAPPER_CLASSES = 'flex w-full flex-col md:max-w-2xl'

const DARK_MODE_PATTERN = /(light|dark)\.[a-z0-9]{8}\.[a-z]+/

const resolveImageModeClasses = (
  baseClassName: string,
  src: ImportedImageSrc,
): string => {
  const match = src.src.match(DARK_MODE_PATTERN)
  if (!match) return baseClassName

  const mode = match[1]
  return mode === 'light'
    ? `${baseClassName} dark:hidden`
    : `${baseClassName} hidden dark:block`
}

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    ...components,

    BodyWrapper({ children }) {
      return (
        <ProseWrapper className={BODY_WRAPPER_CLASSES}>{children}</ProseWrapper>
      )
    },

    InnerHeaderWrapper({ children, className }) {
      return (
        <div className={twMerge(HEADER_WRAPPER_CLASSES, className)}>
          {children}
        </div>
      )
    },

    InnerWrapper({ children, className }) {
      return (
        <div className={twMerge(INNER_WRAPPER_CLASSES, className)}>
          {children}
        </div>
      )
    },

    img: (props) => {
      if (typeof props.src === 'string') {
        // eslint-disable-next-line
        return <img {...props} alt={props.alt || ''} />
      }

      const baseClassName = props.className || ''
      // rehype-mdx-import-media transforms string src into an imported image object at build time
      const src = props.src as unknown as ImportedImageSrc
      const className = resolveImageModeClasses(baseClassName, src)

      return <Image {...props} className={className} />
    },
  }
}

'use client'

import Loading from '@/components/FileSharing/Loading'
import ReturnHome from '@/components/FileSharing/ReturnHome'
import TitleText from '@/components/FileSharing/TitleText'
import { WarningBanner } from '@/components/FileSharing/WarningBanner'
import { claimSecretPaymentToken } from '@/hooks/file-sharing'
import { isSafeRedirect } from '@/utils/safe-redirect'
import { motion } from 'framer-motion'
import { useParams, useSearchParams } from 'next/navigation'
import { type JSX, useEffect, useState } from 'react'

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.4 } },
}

type PageState =
  | { type: 'processing' }
  | { type: 'redirecting' }
  | { type: 'error'; message: string }

/** Post-checkout return handler for paid secrets. Claims the payment token and redirects back. */
export default function SecretCheckoutReturn(): JSX.Element {
  const params = useParams<{ secretId: string }>()
  const searchParams = useSearchParams()
  const secretId = params.secretId
  const [state, setState] = useState<PageState>({ type: 'processing' })

  useEffect(() => {
    const cancelled = searchParams.get('cancelled')
    const sessionId = searchParams.get('session_id')

    if (cancelled) {
      setState({
        type: 'error',
        message:
          'Payment was cancelled. You can try again from the secret link.',
      })
      return
    }

    if (!sessionId) {
      setState({
        type: 'error',
        message:
          'No checkout session found. The payment may not have completed.',
      })
      return
    }

    const claimToken = async () => {
      try {
        const { status } = await claimSecretPaymentToken(secretId, sessionId)

        if (status < 200 || status >= 300) {
          setState({
            type: 'error',
            message:
              'Could not verify payment. Please use the secret link again — your payment has been recorded.',
          })
          return
        }
      } catch {
        setState({
          type: 'error',
          message:
            'Could not verify payment. Please use the secret link again — your payment has been recorded.',
        })
        return
      }

      // Redirect back to the secret viewer
      try {
        const returnUrl = sessionStorage.getItem('rapidly_secret_return')
        sessionStorage.removeItem('rapidly_secret_return')

        if (returnUrl && isSafeRedirect(returnUrl)) {
          setState({ type: 'redirecting' })
          window.location.href = returnUrl
        } else {
          setState({
            type: 'error',
            message:
              'Could not find the original secret link. Please use the secret link again — your payment has been recorded.',
          })
        }
      } catch {
        setState({
          type: 'error',
          message:
            'Could not access storage. Please use the secret link again — your payment has been recorded.',
        })
      }
    }

    claimToken()
  }, [secretId, searchParams])

  if (state.type === 'processing' || state.type === 'redirecting') {
    return (
      <div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
        <Loading
          text={
            state.type === 'redirecting'
              ? 'Payment successful! Redirecting to secret...'
              : 'Processing payment...'
          }
        />
      </div>
    )
  }

  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
      <motion.div
        className="flex w-full max-w-2xl flex-col items-center gap-y-6 text-center"
        variants={fadeIn}
        initial="hidden"
        animate="visible"
      >
        <TitleText>Payment Issue</TitleText>
        <WarningBanner>{state.message}</WarningBanner>
        <ReturnHome />
      </motion.div>
    </div>
  )
}

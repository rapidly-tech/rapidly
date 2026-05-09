'use client'

import Loading from '@/components/FileSharing/Loading'
import ReturnHome from '@/components/FileSharing/ReturnHome'
import TitleText from '@/components/FileSharing/TitleText'
import { WarningBanner } from '@/components/FileSharing/WarningBanner'
import { isSafeRedirect } from '@/utils/safe-redirect'
import { motion } from 'framer-motion'
import { useParams, useSearchParams } from 'next/navigation'
import { JSX, useEffect, useState } from 'react'

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.4 } },
}

type PageState =
  | { type: 'processing' }
  | { type: 'redirecting' }
  | { type: 'error'; message: string }

/** Post-checkout return handler that claims the payment token via API and redirects back to the download page. */
export default function FileShareCheckoutReturn(): JSX.Element {
  const params = useParams<{ slug: string }>()
  const searchParams = useSearchParams()
  const slug = params.slug
  const [state, setState] = useState<PageState>({ type: 'processing' })

  useEffect(() => {
    const cancelled = searchParams.get('cancelled')
    const sessionId = searchParams.get('session_id')

    if (cancelled) {
      setState({
        type: 'error',
        message:
          'Payment was cancelled. You can try again from the download link.',
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

    // Claim the payment token from the server (one-time use).
    // The server sets an httpOnly cookie with the token, so JavaScript
    // never handles the raw token value.
    // Retries with exponential backoff for transient failures.
    const claimToken = async () => {
      const MAX_RETRIES = 3
      let lastError: unknown

      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
          const response = await fetch(
            `/api/file-sharing/channels/${slug}/claim-payment-token`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ checkout_session_id: sessionId }),
            },
          )

          if (response.ok) {
            // Token is now in an httpOnly cookie — no need to store in JS.
            break
          }

          // Client errors (4xx) should not be retried
          if (response.status >= 400 && response.status < 500) {
            setState({
              type: 'error',
              message:
                'Could not verify payment. Please use the download link again — your payment has been recorded.',
            })
            return
          }

          lastError = new Error(`Server responded with ${response.status}`)
        } catch (err) {
          lastError = err
        }

        if (attempt < MAX_RETRIES) {
          await new Promise((r) => setTimeout(r, 1000 * 2 ** attempt))
        }
      }

      if (lastError) {
        setState({
          type: 'error',
          message:
            'Could not verify payment. Please use the download link again — your payment has been recorded.',
        })
        return
      }

      // Read saved hash URL and redirect back
      try {
        const returnUrl = sessionStorage.getItem(`file-sharing:return:${slug}`)
        sessionStorage.removeItem(`file-sharing:return:${slug}`)

        if (returnUrl && isSafeRedirect(returnUrl)) {
          setState({ type: 'redirecting' })
          window.location.href = returnUrl
        } else {
          setState({
            type: 'error',
            message:
              'Could not find the original download link. Please use the download link again — your payment has been recorded.',
          })
        }
      } catch {
        setState({
          type: 'error',
          message:
            'Could not access storage. Please use the download link again — your payment has been recorded.',
        })
      }
    }

    claimToken()
  }, [slug, searchParams])

  if (state.type === 'processing' || state.type === 'redirecting') {
    return (
      <div className="flex min-h-[calc(100vh-200px)] items-center justify-center px-4 py-12">
        <Loading
          text={
            state.type === 'redirecting'
              ? 'Payment successful! Redirecting to download...'
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

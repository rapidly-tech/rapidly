'use client'

/** Renders a full-screen 429 rate limit error page. */
const TooManyRequests = () => {
  return (
    <div className="flex h-screen w-full flex-col items-center justify-center gap-y-16 px-12">
      <h1 className="rp-text-primary text-4xl font-semibold">429</h1>
      <h1 className="max-w-md text-center text-2xl leading-normal text-slate-700 dark:text-slate-300">
        You have been rate limited.
        <br />
        Please try again in 15 minutes.
      </h1>
    </div>
  )
}

export default TooManyRequests

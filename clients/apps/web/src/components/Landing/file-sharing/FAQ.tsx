'use client'

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@rapidly-tech/ui/components/layout/Accordion'

// FAQ — six questions covering the things visitors actually ask
// before they trust a file-sharing service: where the file lives,
// what's encrypted, what we can see, file size, expiry, and
// recipient-side requirements. Answers are intentionally short and
// honest (the customer email today complimented the privacy story —
// the FAQ should reinforce it, not muddy it).

interface QA {
  q: string
  a: string
}

const QUESTIONS: readonly QA[] = [
  {
    q: 'Where does my file actually go?',
    a: 'The file stays on your device. When the recipient opens the link, it streams directly from your browser to theirs over an encrypted peer-to-peer connection. Our server only helps the two browsers find each other.',
  },
  {
    q: "What can Rapidly's server see?",
    a: 'Metadata only — share creation time, expiry, and a slug. The encrypted payload never reaches us. We could not read your files even if compelled to.',
  },
  {
    q: 'How big can the file be?',
    a: 'Up to 1 GB per share. There is no upload step, so you do not wait for it to finish — the file moves only when the recipient is connected.',
  },
  {
    q: 'How long does the link work?',
    a: 'You pick: 1 hour, 1 day, or 1 week. After that, or after the first download (if you set max-downloads to 1), the link is dead. No way to recover it.',
  },
  {
    q: 'Does the recipient need an account?',
    a: 'No. They click the link, the file streams, they download. No signup, no email, no password unless you set one.',
  },
  {
    q: 'What if I close my browser before they download?',
    a: 'The transfer pauses. They can come back when you are online again, or you can re-share the file. iOS users: keep Safari foregrounded — iOS aggressively suspends background tabs and that breaks the connection.',
  },
]

export function FAQ() {
  return (
    <section
      aria-label="Frequently asked questions"
      className="relative z-10 mx-auto w-full max-w-3xl px-4 py-20 md:py-28"
    >
      <div className="mb-10 text-center md:mb-12">
        <h2 className="rp-text-primary text-3xl font-semibold tracking-tight md:text-4xl">
          Questions, answered.
        </h2>
        <p className="rp-text-secondary mx-auto mt-3 max-w-xl text-sm md:text-base">
          Honest answers to the things people ask before trusting a file with
          someone else&apos;s server.
        </p>
      </div>

      <Accordion type="single" collapsible className="flex flex-col gap-3">
        {QUESTIONS.map((item, i) => (
          <AccordionItem
            key={i}
            value={`q-${i}`}
            className="border border-(--beige-border)/50 bg-white shadow-[0_2px_8px_rgba(120,100,80,0.04)] dark:border-white/10 dark:bg-white/5"
          >
            <AccordionTrigger className="rp-text-primary py-4 text-left text-base font-medium tracking-tight">
              {item.q}
            </AccordionTrigger>
            <AccordionContent className="rp-text-secondary pb-4 text-sm leading-relaxed">
              {item.a}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  )
}

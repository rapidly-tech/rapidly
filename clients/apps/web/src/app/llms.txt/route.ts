import index from '@/generated/docs-index.json'
import { CONFIG } from '@/utils/config'

export const dynamic = 'force-static'

// llms.txt — a concise, LLM-friendly map of the documentation.
// https://llmstxt.org
export async function GET() {
  const lines = [
    '# Rapidly',
    '',
    '> Secure file-sharing and paid-content distribution platform.',
    '',
    '## Docs',
    '',
    ...index.pages.map(
      (p) =>
        `- [${p.title}](${CONFIG.FRONTEND_BASE_URL}${p.href})${p.description ? `: ${p.description}` : ''}`,
    ),
    '',
  ]

  return new Response(lines.join('\n'), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  })
}

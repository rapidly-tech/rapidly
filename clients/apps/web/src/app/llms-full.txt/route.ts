import index from '@/generated/docs-index.json'
import { CONFIG } from '@/utils/config'

export const dynamic = 'force-static'

// llms-full.txt — the full documentation text in one LLM-friendly file.
// https://llmstxt.org
export async function GET() {
  const sections = index.pages.map((p) =>
    [
      `# ${p.title}`,
      '',
      `Source: ${CONFIG.FRONTEND_BASE_URL}${p.href}`,
      ...(p.description ? ['', p.description] : []),
      '',
      p.body,
      '',
    ].join('\n'),
  )

  return new Response(sections.join('\n---\n\n'), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  })
}

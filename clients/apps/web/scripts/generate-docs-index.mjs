#!/usr/bin/env node
/**
 * Generates the docs search index consumed by DocsSearch, the llms.txt
 * routes, and the sitemap. Reads every docs page.mdx, extracts the
 * metadata export, headings, and plain text, and writes
 * src/generated/docs-index.json (committed — regenerate with
 * `pnpm docs:index` after editing docs content).
 */
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const docsDir = join(root, 'src/app/(main)/(website)/(landing)/docs')
const outFile = join(root, 'src/generated/docs-index.json')

const SECTION_LABELS = {
  '': 'Getting Started',
  support: 'Getting Started',
  features: 'Features',
  integrate: 'Integrate',
  policies: 'Policies & Fees',
  guides: 'Guides',
  'api-reference': 'API Reference',
  changelog: 'Changelog',
}

// Mirrors rehype-slug (github-slugger) closely enough for our headings.
const slugify = (text) =>
  text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')

const stripMdx = (body) =>
  body
    // code fences: keep the code text, drop the fence markers
    .replace(/^```[^\n]*$/gm, '')
    // JSX tags (keep inner text)
    .replace(/<[^>]+>/g, ' ')
    // markdown links → label
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    // emphasis/inline-code markers
    .replace(/[*_`#>]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const pages = []
const mdxFiles = readdirSync(docsDir, { recursive: true })
  .map(String)
  .filter((f) => f.endsWith(`page.mdx`))
  .sort()

for (const file of mdxFiles) {
  const raw = readFileSync(join(docsDir, file), 'utf8')
  const rel = dirname(file)
  const href = rel === '.' ? '/docs' : `/docs/${rel.split(sep).join('/')}`

  const title =
    raw
      .match(/title:\s*(?:'([^']*)'|"([^"]*)")/)
      ?.slice(1)
      .find(Boolean) ?? href
  const description =
    raw
      .match(/description:\s*(?:'([^']*)'|"([^"]*)")/)
      ?.slice(1)
      .find(Boolean) ?? ''

  // body = everything after the metadata export block
  const body = raw.replace(/^export const metadata = \{[\s\S]*?\}\n/, '')

  const headings = []
  for (const m of body.matchAll(/^(#{2,3})\s+(.+)$/gm)) {
    const text = m[2].trim()
    headings.push({ id: slugify(text), text, level: m[1].length })
  }

  const seg = rel === '.' ? '' : rel.split(sep)[0]
  pages.push({
    href,
    title: title.replace(/\s*\|\s*Rapidly Docs$/, ''),
    description,
    section: SECTION_LABELS[seg] ?? 'Docs',
    headings,
    body: stripMdx(body),
  })
}

mkdirSync(dirname(outFile), { recursive: true })
writeFileSync(outFile, JSON.stringify({ pages }, null, 1) + '\n')
console.log(`docs index: ${pages.length} pages -> ${relative(root, outFile)}`)

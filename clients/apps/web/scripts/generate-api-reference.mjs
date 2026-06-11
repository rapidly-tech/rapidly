#!/usr/bin/env node
/**
 * Transforms the committed OpenAPI snapshot (src/generated/openapi.json,
 * exported from the backend with:
 *   cd server && uv run python -c "import json; from rapidly.app import app; \
 *     json.dump(app.openapi(), open('../clients/apps/web/src/generated/openapi.json','w'))"
 * ) into the curated api-reference.json consumed by the docs API pages.
 * Regenerate with `pnpm docs:api` after the snapshot changes.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const spec = JSON.parse(
  readFileSync(join(root, 'src/generated/openapi.json'), 'utf8'),
)
const outFile = join(root, 'src/generated/api-reference.json')

// Public surface only — matches the coverage of the previous docs site.
const GROUPS = [
  { tag: 'customers', slug: 'customers', title: 'Customers' },
  { tag: 'shares', slug: 'shares', title: 'Shares' },
  { tag: 'files', slug: 'files', title: 'Files' },
  { tag: 'events', slug: 'events', title: 'Events' },
  { tag: 'metrics', slug: 'metrics', title: 'Metrics' },
  { tag: 'webhooks', slug: 'webhooks', title: 'Webhooks' },
  { tag: 'workspaces', slug: 'workspaces', title: 'Workspaces' },
  { tag: 'oauth2', slug: 'oauth2', title: 'OAuth 2.0' },
]

const deref = (node) => {
  if (!node || typeof node !== 'object') return node
  if (node.$ref) {
    const name = node.$ref.split('/').pop()
    return { name, ...(spec.components?.schemas?.[name] ?? {}) }
  }
  return node
}

const schemaType = (schema) => {
  const s = deref(schema)
  if (!s) return 'unknown'
  if (s.anyOf) {
    return s.anyOf
      .map(schemaType)
      .filter((t, i, a) => a.indexOf(t) === i)
      .join(' | ')
  }
  if (s.enum) return s.enum.map((v) => JSON.stringify(v)).join(' | ')
  if (s.type === 'array') return `${schemaType(s.items)}[]`
  if (s.type === 'object' && s.name) return s.name
  return s.type ?? s.name ?? 'object'
}

const bodyFields = (schema) => {
  const s = deref(schema)
  if (!s?.properties) return []
  const required = new Set(s.required ?? [])
  return Object.entries(s.properties).map(([name, prop]) => {
    const p = deref(prop)
    return {
      name,
      type: schemaType(prop),
      required: required.has(name),
      description: p.description ?? p.title ?? '',
    }
  })
}

const curlFor = (method, path, op) => {
  const lines = [`curl -X ${method.toUpperCase()} \\`]
  lines.push(`  https://api.rapidly.tech${path} \\`)
  lines.push(`  -H "Authorization: Bearer $RAPIDLY_ACCESS_TOKEN"`)
  if (op.requestBody) {
    lines[lines.length - 1] += ' \\'
    lines.push(`  -H "Content-Type: application/json" \\`)
    lines.push(`  -d '{ ... }'`)
  }
  return lines.join('\n')
}

const groups = GROUPS.map(({ tag, slug, title }) => {
  const operations = []
  for (const [path, item] of Object.entries(spec.paths)) {
    for (const [method, op] of Object.entries(item)) {
      if (!['get', 'post', 'put', 'patch', 'delete'].includes(method)) continue
      if (!(op.tags ?? []).includes(tag)) continue
      const params = (op.parameters ?? []).map((p) => ({
        name: p.name,
        in: p.in,
        required: p.required ?? false,
        type: schemaType(p.schema),
        description: deref(p.schema)?.description ?? p.description ?? '',
      }))
      const reqSchema =
        op.requestBody?.content?.['application/json']?.schema ?? null
      const okResponse = Object.entries(op.responses ?? {}).find(([code]) =>
        code.startsWith('2'),
      )
      operations.push({
        id: (op.summary ?? `${method} ${path}`)
          .toLowerCase()
          .replace(/[^\w\s-]/g, '')
          .replace(/\s+/g, '-'),
        method: method.toUpperCase(),
        path,
        summary: op.summary ?? `${method.toUpperCase()} ${path}`,
        description: op.description ?? '',
        params,
        body: reqSchema ? bodyFields(reqSchema) : [],
        bodyName: reqSchema ? schemaType(reqSchema) : null,
        responseCode: okResponse?.[0] ?? null,
        responseName: okResponse
          ? schemaType(
              okResponse[1]?.content?.['application/json']?.schema ?? null,
            )
          : null,
        curl: curlFor(method, path, op),
      })
    }
  }
  return { slug, title, operations }
}).filter((g) => g.operations.length > 0)

writeFileSync(outFile, JSON.stringify({ groups }, null, 1) + '\n')
console.log(
  `api reference: ${groups.length} groups, ${groups.reduce((n, g) => n + g.operations.length, 0)} operations`,
)

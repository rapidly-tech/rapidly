import { twMerge } from 'tailwind-merge'

export interface ApiParam {
  name: string
  in: string
  required: boolean
  type: string
  description: string
}

export interface ApiBodyField {
  name: string
  type: string
  required: boolean
  description: string
}

export interface ApiOperation {
  id: string
  method: string
  path: string
  summary: string
  description: string
  params: ApiParam[]
  body: ApiBodyField[]
  bodyName: string | null
  responseCode: string | null
  responseName: string | null
  curl: string
}

const METHOD_CLASSES: Record<string, string> = {
  GET: 'bg-slate-900/5 text-slate-700 dark:bg-white/10 dark:text-slate-300',
  POST: 'bg-slate-900 text-white dark:bg-white dark:text-slate-900',
  PATCH: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  PUT: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  DELETE: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
}

const MethodBadge = ({ method }: { method: string }) => (
  <span
    className={twMerge(
      'rounded-md px-2 py-0.5 font-mono text-xs font-semibold',
      METHOD_CLASSES[method] ?? METHOD_CLASSES.GET,
    )}
  >
    {method}
  </span>
)

const FieldRow = ({
  name,
  type,
  required,
  description,
}: {
  name: string
  type: string
  required: boolean
  description: string
}) => (
  <div className="border-b border-slate-100 py-2.5 last:border-0 dark:border-slate-800">
    <div className="flex flex-wrap items-baseline gap-2 font-mono text-sm">
      <span className="font-medium text-slate-900 dark:text-white">{name}</span>
      <span className="break-all text-slate-500 dark:text-slate-400">
        {type}
      </span>
      {required && (
        <span className="text-xs text-amber-600 dark:text-amber-400">
          required
        </span>
      )}
    </div>
    {description && (
      <p className="m-0! mt-1 text-sm text-slate-500 dark:text-slate-400">
        {description}
      </p>
    )}
  </div>
)

/** One endpoint: heading (anchors into the TOC rail), method + path,
 * parameter/body tables, response, and a curl example. */
export const Operation = ({ op }: { op: ApiOperation }) => {
  const queryParams = op.params.filter((p) => p.in === 'query')
  const pathParams = op.params.filter((p) => p.in === 'path')

  return (
    <section className="border-b border-slate-200 pb-10 last:border-0 dark:border-slate-800">
      <h2 id={op.id} className="scroll-mt-28">
        {op.summary}
      </h2>
      <p className="flex flex-wrap items-center gap-2">
        <MethodBadge method={op.method} />
        <code className="text-sm break-all">{op.path}</code>
      </p>
      {op.description && <p>{op.description}</p>}

      {pathParams.length > 0 && (
        <>
          <h3 id={`${op.id}-path-parameters`} className="scroll-mt-28">
            Path parameters
          </h3>
          <div>
            {pathParams.map((p) => (
              <FieldRow key={p.name} {...p} />
            ))}
          </div>
        </>
      )}

      {queryParams.length > 0 && (
        <>
          <h3 id={`${op.id}-query-parameters`} className="scroll-mt-28">
            Query parameters
          </h3>
          <div>
            {queryParams.map((p) => (
              <FieldRow key={p.name} {...p} />
            ))}
          </div>
        </>
      )}

      {op.body.length > 0 && (
        <>
          <h3 id={`${op.id}-request-body`} className="scroll-mt-28">
            Request body{' '}
            {op.bodyName && (
              <code className="text-sm font-normal">{op.bodyName}</code>
            )}
          </h3>
          <div>
            {op.body.map((f) => (
              <FieldRow key={f.name} {...f} />
            ))}
          </div>
        </>
      )}

      {op.responseName && (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Returns <code>{op.responseCode}</code> with{' '}
          <code>{op.responseName}</code>.
        </p>
      )}

      <pre className="overflow-x-auto">
        <code>{op.curl}</code>
      </pre>
    </section>
  )
}

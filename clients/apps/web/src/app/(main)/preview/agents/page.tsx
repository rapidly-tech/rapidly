import { redirect } from 'next/navigation'

/**
 * /preview/agents → /preview/agents/workflows.
 *
 * The chamber's first meaningful surface is the workflows
 * list; treat a bare visit to /agents as if the operator
 * clicked the first sidebar entry.
 */
export default function AgentsIndexPage(): never {
  redirect('/preview/agents/workflows')
}

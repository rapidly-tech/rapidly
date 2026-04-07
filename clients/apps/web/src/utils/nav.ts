import { CONFIG } from '@/utils/config'
import { schemas } from '@rapidly-tech/client'

export const workspacePageLink = (
  org: schemas['Workspace'] | schemas['CustomerWorkspace'],
  path?: string,
): string => {
  return `${CONFIG.FRONTEND_BASE_URL}/${org.slug}/${path ?? ''}`
}

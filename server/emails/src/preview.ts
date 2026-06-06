/** Sample preview data for email template development in the React Email studio. */
import { schemas } from './types'

type DeepPartial<T> = T extends object
  ? {
      [P in keyof T]?: DeepPartial<T[P]>
    }
  : T

export const workspace: Partial<schemas['Workspace']> = {
  name: 'Acme Inc.',
  slug: 'acme-inc',
  avatar_url:
    'https://sandbox-uploads.rapidly.tech/organization_avatar/b3281d01-7b90-4a5b-8225-e8e150f4009c/9e5f848b-8b1d-4592-9fe1-7cad2cfa53ee/unicorn-dev-logo.png',
  website: 'https://www.example.com',
}

import { resolveApiUrl } from '@/utils/api'
import { schemas } from '@rapidly-tech/client'
import Avatar from '@rapidly-tech/ui/components/data/Avatar'
import Button from '@rapidly-tech/ui/components/forms/Button'
import { List, ListItem } from '@rapidly-tech/ui/components/layout/List'
import SharedLayout from './components/SharedLayout'

type AuthorizeSubject = schemas['AuthorizeUser'] | schemas['AuthorizeWorkspace']

const isSubTypeWorkspace = (
  sub_type: string,
  _sub: AuthorizeSubject,
): _sub is schemas['AuthorizeWorkspace'] => sub_type === 'workspace'

const isSubTypeUser = (
  sub_type: string,
  _sub: AuthorizeSubject,
): _sub is schemas['AuthorizeUser'] => sub_type === 'user'

const groupScopesByCategory = (
  scopes: schemas['Scope'][],
): Record<string, schemas['Scope'][]> =>
  scopes.reduce<Record<string, schemas['Scope'][]>>((groups, scope) => {
    const category = scope.split(':')[0]
    const existing = groups[category] ?? []
    return { ...groups, [category]: [...existing, scope] }
  }, {})

const formatScopeCategory = (key: string): string =>
  key === 'openid' ? 'OpenID' : key.replaceAll('_', ' ')

const SubjectBadge = ({
  avatarUrl,
  name,
  label,
}: {
  avatarUrl: string | null
  name: string
  label: string
}) => (
  <div className="glass-elevated mt-6 mb-0 inline-flex flex-row items-center justify-start gap-2 rounded-2xl p-2 pr-4 text-sm">
    <Avatar className="h-8 w-8" avatar_url={avatarUrl} name={name} />
    {label}
  </div>
)

const PermissionIntro = ({
  clientName,
  targetDescription,
  children,
}: {
  clientName: string
  targetDescription: string
  children: React.ReactNode
}) => (
  <>
    <div className="w-full text-center text-lg text-slate-600 dark:text-slate-400">
      <span className="font-medium">{clientName}</span> requests the following
      permissions to your {targetDescription}.
    </div>
    {children}
  </>
)

const ScopeList = ({
  scopes,
  displayNames,
}: {
  scopes: schemas['Scope'][]
  displayNames: Record<string, string>
}) => (
  <div className="mb-6 w-full">
    <List size="small">
      {Object.entries(groupScopesByCategory(scopes)).map(
        ([category, categoryScopes]) => (
          <ListItem
            key={category}
            className="glass-surface flex flex-col items-start gap-y-1 py-3 text-sm"
            size="small"
          >
            <h3 className="font-medium capitalize">
              {formatScopeCategory(category)}
            </h3>
            <ul>
              {categoryScopes.map((scope) => (
                <li
                  key={scope}
                  className="text-sm text-slate-500 dark:text-slate-400"
                >
                  {displayNames[scope]}
                </li>
              ))}
            </ul>
          </ListItem>
        ),
      )}
    </List>
  </div>
)

const TermsFooter = ({
  clientName,
  tosUri,
  policyUri,
}: {
  clientName: string
  tosUri?: string | null
  policyUri?: string | null
}) => {
  if (!tosUri && !policyUri) return null

  const linkClass = 'dark:text-slate-500 text-slate-700'

  return (
    <div className="mt-8 text-center text-sm text-slate-500 dark:text-slate-400">
      Before using this app, you can review {clientName}&apos;s{' '}
      {tosUri && tosUri.startsWith('https://') && (
        <a className={linkClass} href={tosUri}>
          Terms of Service
        </a>
      )}
      {tosUri &&
        tosUri.startsWith('https://') &&
        policyUri &&
        policyUri.startsWith('https://') &&
        ' and '}
      {policyUri && policyUri.startsWith('https://') && (
        <a className={linkClass} href={policyUri}>
          Privacy Policy
        </a>
      )}
      .
    </div>
  )
}

const AuthorizePage = ({
  authorizeResponse: { client, scopes, sub_type, sub, scope_display_names },
  searchParams,
}: {
  authorizeResponse:
    | schemas['AuthorizeResponseUser']
    | schemas['AuthorizeResponseWorkspace']
  searchParams: Record<string, string>
}) => {
  const actionURL = `${resolveApiUrl()}/api/oauth2/consent?${new URLSearchParams(searchParams).toString()}`
  const clientName = client.client_name || client.client_id

  const introduction = (
    <>
      {sub && isSubTypeWorkspace(sub_type, sub) && (
        <PermissionIntro
          clientName={clientName}
          targetDescription="Rapidly workspace"
        >
          <SubjectBadge
            avatarUrl={sub.avatar_url}
            name={sub.slug}
            label={sub.slug}
          />
        </PermissionIntro>
      )}
      {sub && isSubTypeUser(sub_type, sub) && (
        <PermissionIntro
          clientName={clientName}
          targetDescription="personal Rapidly account"
        >
          <SubjectBadge
            avatarUrl={sub.avatar_url}
            name={sub.email}
            label={sub.email}
          />
        </PermissionIntro>
      )}
    </>
  )

  return (
    <SharedLayout client={client} introduction={introduction}>
      <form method="post" action={actionURL}>
        <ScopeList scopes={scopes} displayNames={scope_display_names} />

        <div className="flex w-full flex-col gap-3">
          <Button className="grow" type="submit" name="action" value="allow">
            Allow
          </Button>
          <Button
            variant="secondary"
            className="grow"
            type="submit"
            name="action"
            value="deny"
          >
            Deny
          </Button>
        </div>

        <TermsFooter
          clientName={clientName}
          tosUri={client.tos_uri}
          policyUri={client.policy_uri}
        />
      </form>
    </SharedLayout>
  )
}

export default AuthorizePage

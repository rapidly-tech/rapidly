import { ROUTES } from '@/utils/routes'
import { redirect } from 'next/navigation'

/** Account index page that redirects to the account preferences section. */
export default function Page() {
  return redirect(ROUTES.DASHBOARD.ACCOUNT_PREFERENCES)
}

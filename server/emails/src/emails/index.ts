/** Registry mapping template names to React email components for server-side rendering. */

import { CustomerSessionCode } from './customer_session_code'
import { EmailUpdate } from './email_update'
import { LoginCode } from './login_code'
import { NotificationCreateAccount } from './notification_create_account'
import { NotificationCreditsGranted } from './notification_credits_granted'
import { NotificationFileShareDownloadCompleted } from './notification_file_share_download_completed'
import { NotificationFileSharePaymentReceived } from './notification_file_share_payment_received'
import { NotificationFileShareSessionExpired } from './notification_file_share_session_expired'
import { OAuth2LeakedClient } from './oauth2_leaked_client'
import { OAuth2LeakedToken } from './oauth2_leaked_token'
import { OrganizationAccessTokenLeaked } from './organization_access_token_leaked'
import { OrganizationAccountUnlink } from './organization_account_unlink'
import { OrganizationInvite } from './organization_invite'
import OrganizationReviewed from './organization_reviewed'
import { OrganizationUnderReview } from './organization_under_review'
import { WebhookEndpointDisabled } from './webhook_endpoint_disabled'

const TEMPLATES: Record<string, React.FC<any>> = {
  login_code: LoginCode,
  customer_session_code: CustomerSessionCode,
  email_update: EmailUpdate,
  oauth2_leaked_client: OAuth2LeakedClient,
  oauth2_leaked_token: OAuth2LeakedToken,
  organization_access_token_leaked: OrganizationAccessTokenLeaked,
  organization_account_unlink: OrganizationAccountUnlink,
  organization_invite: OrganizationInvite,
  organization_under_review: OrganizationUnderReview,
  organization_reviewed: OrganizationReviewed,
  webhook_endpoint_disabled: WebhookEndpointDisabled,
  notification_create_account: NotificationCreateAccount,
  notification_credits_granted: NotificationCreditsGranted,
  notification_file_share_download_completed:
    NotificationFileShareDownloadCompleted,
  notification_file_share_session_expired: NotificationFileShareSessionExpired,
  notification_file_share_payment_received:
    NotificationFileSharePaymentReceived,
}

export default TEMPLATES

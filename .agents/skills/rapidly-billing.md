# Rapidly Payment & File Sharing System

Comprehensive guide to Rapidly's payment infrastructure, covering file sharing channels, paid downloads via Stripe Connect, the platform fee model, and supporting entities.

## Quick Reference

```
Channel Created (free or paid)
    ↓
WebRTC P2P File Transfer
    ↓ (if paid)
Stripe Checkout Session (Direct Charge on seller's Connect account)
    → 5% platform fee (application_fee_amount)
    → Payment token unlocks download
    ↓
Download Completed → Slot Claimed
```

## Table of Contents

1. [Core Entities](#1-core-entities)
2. [Entity Relationships](#2-entity-relationships)
3. [Main Services](#3-main-services)
4. [Background Tasks](#4-background-tasks)
5. [Stripe Integration](#5-stripe-integration)
6. [File Sharing Lifecycle](#6-file-sharing-lifecycle)
7. [Paid Channel Payment Flow](#7-paid-channel-payment-flow)
8. [Secret Exchange](#8-secret-exchange)
9. [Storefront & Digital Downloads](#9-storefront--digital-downloads)
10. [WebRTC / ICE Configuration](#10-webrtc--ice-configuration)
11. [Key File Locations](#11-key-file-locations)

---

## 1. Core Entities

### FileShareSession
**File:** `server/rapidly/models/file_share_session.py`

Represents a file-sharing session (channel) with optional pricing.

| Field | Type | Description |
|-------|------|-------------|
| `short_slug` | str | Short alphanumeric slug for URLs |
| `long_slug` | str | Human-readable slug |
| `status` | FileShareSessionStatus | created, active, completed, expired, destroyed, reported |
| `max_downloads` | int | Download limit (0 = unlimited) |
| `download_count` | int | Current download count |
| `price_cents` | int \| None | Price in cents (None = free) |
| `currency` | str | ISO 4217 currency code (default "usd") |
| `title` | str \| None | Custom display title |
| `file_name` | str \| None | Display name for the file |
| `file_size_bytes` | int \| None | File size for display |
| `ttl_seconds` | int \| None | Time-to-live for the session |
| `expires_at` | datetime \| None | Expiration timestamp |
| `creator_ip_hash` | str \| None | Hashed IP of channel creator |

**Relationships:** user (optional), organization (optional), product (optional, for paid channels)

---

### FileSharePayment
**File:** `server/rapidly/models/file_share_payment.py`

Tracks a Stripe payment for a paid file download.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | UUID | FK to FileShareSession |
| `status` | FileSharePaymentStatus | pending, completed, refunded, failed |
| `amount_cents` | int | Payment amount in cents |
| `currency` | str | ISO 4217 currency code |
| `platform_fee_cents` | int | Rapidly's platform fee (5%) |
| `stripe_checkout_session_id` | str \| None | Stripe Checkout Session ID |
| `stripe_payment_intent_id` | str \| None | Stripe PaymentIntent ID |
| `buyer_email` | str \| None | Buyer contact |
| `buyer_name` | str \| None | Buyer name |

**Relationships:** session (FileShareSession), customer (optional), payment (optional link to Payment model)

---

### FileShareDownload
**File:** `server/rapidly/models/file_share_download.py`

Audit record for each completed download in a file sharing session.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | UUID | FK to FileShareSession |
| `slot_number` | int | Which download slot was consumed |
| `downloader_ip_hash` | str \| None | Hashed IP of downloader |

---

### FileShareReport
**File:** `server/rapidly/models/file_share_report.py`

Abuse/violation report for a file sharing session.

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | UUID | FK to FileShareSession |
| `status` | FileShareReportStatus | reviewed, dismissed, actioned |
| `reporter_ip_hash` | str \| None | Hashed IP of reporter |
| `admin_notes` | str \| None | Admin review notes |
| `reviewed_at` | datetime \| None | When report was reviewed |

---

### Product & ProductPrice
**Files:** `server/rapidly/models/product.py`, `server/rapidly/models/product_price.py`

Products are created automatically for paid file sharing channels. Each paid channel gets a `Product` with a `ProductPriceFixed` entry.

| ProductPrice Types | Description |
|-------------------|-------------|
| `ProductPriceFixed` | Fixed amount (used for paid file shares) |
| `ProductPriceCustom` | Merchant sets at checkout |
| `ProductPriceFree` | Zero cost |

**Product visibility:** `public` or `private`. Paid file shares create products with `visibility=public` and `user_metadata={"type": "file_share"}`.

---

### Payment
**File:** `server/rapidly/models/payment.py`

Individual payment transaction record synced from Stripe charges.

| Field | Type | Description |
|-------|------|-------------|
| `status` | PaymentStatus | pending, succeeded, failed |
| `processor_id` | str | Stripe charge ID |
| `method` | str | card, bank_transfer, etc. |
| `amount`, `currency` | int, str | Payment amount |
| `decline_reason` | str | Why payment failed |
| `risk_level`, `risk_score` | str, int | Fraud assessment |

---

### Customer
**File:** `server/rapidly/models/customer.py`

| Field | Type | Description |
|-------|------|-------------|
| `email`, `name` | str | Contact info |
| `stripe_customer_id` | str | Stripe link |
| `billing_address` | Address | Stored address |

---

### Wallet & WalletTransaction
**Files:** `server/rapidly/models/wallet.py`, `server/rapidly/models/wallet_transaction.py`

Ledger-style wallet whose balance is computed as the sum of its transactions. Each customer may have one wallet per (type, currency) combination.

| Wallet Type | Description |
|-------------|-------------|
| `usage` | Metered usage tracking |
| `billing` | Prepaid billing credit |

---

## 2. Entity Relationships

```
Organization
├── Product (auto-created for paid file shares)
│   └── ProductPrice (ProductPriceFixed)
├── Customer
│   └── Wallet → WalletTransaction
├── FileShareSession
│   ├── FileSharePayment (for paid channels)
│   ├── FileShareDownload (per completed download)
│   └── FileShareReport (abuse reports)
├── Account (for Stripe Connect payouts)
└── Storefront (public-facing digital downloads page)

Payment (from Stripe charge sync)
└── linked to FileSharePayment (optional)
```

---

## 3. Main Services

### FileSharingService
**File:** `server/rapidly/file_sharing/service.py`

Core service orchestrating channels, secrets, payments, and WebRTC:

```python
# Channel lifecycle
create_channel(redis, max_downloads, ttl, price_cents, ...) → ChannelCreateResponse
fetch_channel(redis, slug, reader_token, payment_token) → ChannelFetchResponse | None
renew_channel(redis, slug, secret, ttl) → ChannelRenewResponse
destroy_channel(redis, slug, secret) → ChannelDestroyResponse

# Payments
create_checkout(redis, slug) → ChannelCheckoutResponse | None

# Downloads
record_download_complete(redis, slug, reader_token) → DownloadCompleteResponse

# Secrets
create_secret(redis, message, expiration) → SecretCreateResponse
create_file_secret(redis, message, expiration) → SecretCreateResponse
fetch_secret(redis, secret_id) → SecretFetchResponse | None
fetch_file_secret(redis, file_id) → SecretFetchResponse | None

# Access control
set_reader_token(redis, slug, secret, token_hash) → ReaderTokenResponse
record_password_attempt(redis, slug, secret) → PasswordAttemptResponse

# WebRTC
get_ice_config_for_channel(redis, slug, token) → ICEConfigResponse | None
build_ice_config() → ICEConfigResponse

# Reporting
report_channel(redis, slug, reader_token) → ReportResponse

# PG-backed queries (authenticated)
list_sessions(session, auth_subject, pagination, ...) → (list, int)
get_session_detail(session, auth_subject, session_id) → FileShareSession | None
get_session_reports(session, auth_subject, session_id) → list | None
update_session_report(session, auth_subject, report_id, status, ...) → FileShareReport | None
```

### StorefrontService
**File:** `server/rapidly/storefront/service.py`

Public-facing product catalogue and file-share listing:

```python
get(session, slug) → Organization | None
list_public_file_shares(session, organization_id) → Sequence[FileShareSession]
list_customers(session, organization, pagination) → (Sequence[Customer], int)
```

### StripeConnectService
**File:** `server/rapidly/stripe_connect/service.py`

Stripe Connect account lifecycle:

```python
get_balance(session, auth_subject, organization_id) → StripeBalance
list_payouts(session, auth_subject, organization_id, ...) → StripePayoutList
```

### PaymentService
**File:** `server/rapidly/payment/service.py`

```python
list(session, auth_subject, ...) → (Sequence[Payment], int)
get(session, auth_subject, id) → Payment | None
upsert_from_stripe_charge(session, charge, wallet) → Payment
```

---

## 4. Background Tasks

### File Sharing Tasks
**File:** `server/rapidly/file_sharing/jobs.py`

| Task | Trigger | Action |
|------|---------|--------|
| `file_sharing.session_created` | Channel creation (org-scoped) | Send webhook to organization |
| `file_sharing.download_completed` | Download recorded | Send webhook notification |
| `file_sharing.expire_sessions` | Scheduled cron | Mark expired sessions |

### Stripe Webhook Tasks
**File:** `server/rapidly/integrations/stripe/jobs.py`

| Task | Stripe Event | Action |
|------|--------------|--------|
| `stripe.webhook.account.updated` | Account info changed | Sync Connect account status |
| `charge.succeeded` | Payment complete | Update payment record |
| `charge.failed` | Payment failed | Mark payment failed |
| `payout.paid` | Payout complete | Update payout status |

---

## 5. Stripe Integration

### Architecture: Stripe Connect Direct Charges

Rapidly uses **Stripe Connect with Direct Charges**. Sellers connect their Stripe accounts via Express onboarding. When a buyer pays for a file download:

1. A Stripe Checkout Session is created on the **seller's connected account**
2. The platform collects a 5% application fee automatically
3. The buyer pays the seller directly; Rapidly never holds funds

### Platform Fee

```python
# server/rapidly/config.py
FILE_SHARING_PLATFORM_FEE_PERCENT = 500  # 5% in basis points

# Calculation in file_sharing/service.py
fee_amount = int(price_cents * (FILE_SHARING_PLATFORM_FEE_PERCENT / 10000))
```

### StripeService
**File:** `server/rapidly/integrations/stripe/service.py`

Key methods:
- `create_account()` - Create Express Connect account
- `create_checkout_session_direct()` - Direct Charge checkout on connected account
- `retrieve_intent()` - Get payment intent details
- `create_account_link()` - Onboarding link for Express accounts

### Webhook Endpoints
**File:** `server/rapidly/integrations/stripe/routes.py`

- `/v1/integrations/stripe/webhook` - Direct webhooks
- `/v1/integrations/stripe/webhook-connect` - Connect account webhooks

### Webhook Processing Flow

```
Stripe POST → Verify signature → ExternalEvent.enqueue()
                                        ↓
                               Store in external_events table
                                        ↓
                               Enqueue Dramatiq task
                                        ↓
                               Worker processes async
                                        ↓
                               Mark handled_at on success
```

---

## 6. File Sharing Lifecycle

### Channel Creation Flow

```
1. Client calls POST /api/file-sharing/channels
   - max_downloads, ttl, price_cents (optional), file_name, etc.
2. FileSharingService.create_channel():
   a. If paid + org-scoped: create Product with ProductPriceFixed
   b. Create channel in Redis (ChannelRepository)
   c. PG dual-write: create FileShareSession record
   d. If org-scoped: dispatch "file_sharing.session_created" webhook task
3. Return: { secret, longSlug, shortSlug }
```

### Channel Fetch (Download Page)

```
1. Downloader visits /<slug>
2. Client calls GET /api/file-sharing/channels/<slug>
3. FileSharingService.fetch_channel():
   a. Look up channel in Redis
   b. Block if pending-token registration
   c. Validate reader_token if registered
   d. Check download slots available
   e. For paid channels: check payment_token or set payment_required=true
4. Return: { available, price_cents, currency, file_name, file_size_bytes, payment_required }
```

### Download Completion (Slot Claiming)

```
1. WebRTC P2P transfer completes
2. Client calls POST /api/file-sharing/channels/<slug>/download-complete
3. FileSharingService.record_download_complete():
   a. Atomically claim a download slot in Redis
   b. PG dual-write: create FileShareDownload record
4. Return: { success, remaining }
```

Slots are claimed on download completion, NOT on channel fetch. This avoids wasting slots on page reloads or failed WebRTC connections.

### Channel Destruction

```
1. Owner calls DELETE /api/file-sharing/channels/<slug>
   - Requires channel ownership secret
2. First request: marks channel for destruction with 30-second delay
3. Second request (within delay): confirms immediate destruction
4. Owner can cancel by renewing the channel
```

### Reporting Flow

```
1. Downloader calls POST /api/file-sharing/channels/<slug>/report
   - Requires valid reader_token (prevents anonymous DoS)
2. FileSharingService.report_channel():
   a. Validate reader token
   b. Close signaling room (disconnects peers)
   c. Delete channel from Redis
   d. PG dual-write: create FileShareReport, mark session as reported
```

---

## 7. Paid Channel Payment Flow

### Checkout Flow

```
1. Downloader sees payment_required=true on channel fetch
2. Client calls POST /api/file-sharing/channels/<slug>/checkout
3. FileSharingService.create_checkout():
   a. Look up channel in Redis, verify it's paid
   b. Calculate application fee: price * 5%
   c. Generate payment_token (secrets.token_urlsafe)
   d. Store token hash in Redis (valid for channel TTL)
   e. Call stripe_service.create_checkout_session_direct():
      - connected_account_id = seller's Stripe account
      - application_fee_amount = calculated platform fee
      - success_url includes payment_token in query params
      - metadata: platform, channel_slug, user_id, product_id
   f. PG dual-write: create FileSharePayment record
4. Return: { checkout_url, session_id }
5. Buyer redirected to Stripe Checkout
6. After payment, buyer redirected to success_url with payment_token
7. payment_token is passed on subsequent fetch_channel calls to bypass payment_required
```

### Payment Token Validation

```
1. Buyer passes payment_token on channel fetch
2. ChannelRepository.validate_payment_token():
   - Hash the token with SHA-256
   - Compare against stored hash in Redis
3. If valid: payment_required=false, download proceeds
```

---

## 8. Secret Exchange

One-time secrets for secure text and file exchange, backed by Redis with configurable TTL.

### Text Secrets

```python
create_secret(redis, message, expiration)   # Store encrypted message
fetch_secret(redis, secret_id)              # Retrieve and delete (one-time read)
```

### File Secrets

```python
create_file_secret(redis, message, expiration)  # Store encrypted file data
fetch_file_secret(redis, file_id)               # Retrieve and delete
```

Secrets are OpenPGP-encrypted on the client side. The server only stores and retrieves ciphertext. Max payload: 1MB. TTL range: 60 seconds to 7 days.

---

## 9. Storefront & Digital Downloads

Organizations can enable a public storefront page that lists their active paid file shares.

### Storefront Route
**File:** `server/rapidly/storefront/routes.py`

```
GET /storefronts/<slug>
```

Returns:
- Organization info
- Active paid file shares (FileShareSession with price_cents > 0, status=active)
- Recent customer summary (names/initials)

### Storefront Service
**File:** `server/rapidly/storefront/service.py`

```python
# Filters: org must have storefront_enabled=True, not deleted, not blocked
get(session, slug) → Organization | None

# Lists active paid sessions for the org
list_public_file_shares(session, organization_id) → Sequence[FileShareSession]
```

---

## 10. WebRTC / ICE Configuration

### Signaling Server
**File:** `server/rapidly/file_sharing/signaling.py`

WebSocket-based signaling server for P2P file transfers. Relays SDP offers/answers and ICE candidates between peers. Never sees file content.

Room model:
- Each channel slug maps to one room
- One uploader (validated by channel secret)
- Multiple downloaders (validated by reader token)

**Note:** Rooms are in-memory. Single-process deployment required, or use Redis pub/sub for multi-process.

### ICE Configuration
**File:** `server/rapidly/file_sharing/service.py` (`build_ice_config()`)

- Always includes STUN server
- TURN credentials generated via HMAC-SHA1 (COTURN ephemeral auth)
- Optional TURNS (TLS) when `FILE_SHARING_TURN_TLS_ENABLED=true`

---

## 11. Key File Locations

### Models
```
server/rapidly/models/
├── file_share_session.py      # Core session model
├── file_share_payment.py      # Payment tracking for paid downloads
├── file_share_download.py     # Download audit records
├── file_share_report.py       # Abuse reports
├── product.py                 # Product catalog (auto-created for paid shares)
├── product_price.py           # Price definitions
├── payment.py                 # Stripe charge records
├── customer.py                # Customer records
├── wallet.py                  # Customer wallets
└── wallet_transaction.py      # Wallet ledger entries
```

### Services
```
server/rapidly/
├── file_sharing/
│   ├── service.py             # Core file sharing orchestration
│   ├── repository.py          # Redis-backed channel/secret operations
│   ├── pg_repository.py       # PostgreSQL audit trail repositories
│   ├── signaling.py           # WebSocket signaling for WebRTC
│   ├── redis_scripts.py       # Lua scripts for atomic Redis ops
│   ├── routes.py              # API endpoints
│   ├── schemas.py             # Pydantic request/response models
│   ├── access.py              # Access control dependencies
│   ├── jobs.py                # Background tasks (webhooks, expiry)
│   ├── slugs.py               # Slug generation
│   ├── wordlist.py            # Word list for human-readable slugs
│   └── utils.py               # Helpers
├── storefront/
│   ├── service.py             # Public storefront queries
│   ├── routes.py              # GET /storefronts/<slug>
│   └── schemas.py             # Storefront response schemas
├── stripe_connect/
│   ├── service.py             # Connect account lifecycle, balance, payouts
│   ├── routes.py              # Stripe Connect API endpoints
│   └── schemas.py             # Balance, payout schemas
├── payment/
│   ├── service.py             # Payment record CRUD, Stripe charge sync
│   ├── repository.py          # Payment queries
│   └── routes.py              # Payment listing endpoints
└── product/
    ├── service.py             # Product catalog management
    ├── repository.py          # Product queries
    └── routes.py              # Product API endpoints
```

### Stripe Integration
```
server/rapidly/integrations/stripe/
├── routes.py       # Webhook endpoints
├── service.py      # Stripe API wrapper (accounts, checkout, charges)
├── jobs.py         # Webhook processing tasks
└── utils.py        # Helpers
```

---

## Common Debugging Scenarios

### Payment Not Going Through
1. Check FileSharePayment record for `status` and `stripe_checkout_session_id`
2. Verify seller's Stripe Connect account is fully onboarded
3. Check that `price_cents` and `seller_stripe_id` are set on the channel in Redis
4. Look at external_events for Stripe webhook delivery

### Download Slot Not Claimed
1. Check Redis channel state for remaining download count
2. Verify `record_download_complete` was called (not just `fetch_channel`)
3. Check FileShareDownload PG records for the session

### Channel Not Found
1. Check if TTL expired in Redis (`channel:short:<slug>` key)
2. Check FileShareSession PG record for `status` (may be destroyed/reported)
3. If paid, verify payment_token is valid and not expired

### Storefront Not Showing Files
1. Verify organization has `storefront_enabled=True`
2. Check FileShareSession `status=active` and `price_cents > 0`
3. Ensure sessions are not expired or destroyed

### Platform Fee Calculation
```python
# 5% fee = 500 basis points
fee_amount = int(price_cents * (500 / 10000))
# Example: $10.00 (1000 cents) → fee = 50 cents ($0.50)
```

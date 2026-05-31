# M7 — Construction integrations + MCP hosting

Executable plan for milestone M7 of `RAPIDLY_ENGINEERING_SUITE_PLAN.md`.
M7 connects the engineering suite to the vendor systems engineering
firms actually run their projects in (Bentley ProjectWise, Autodesk
ACC, Aconex) and formalises the path for LLM-tool extension via MCP.

**Read M4 + M6 first.** M7 builds on M4's `IntegrationCredential`
encrypted store, M4's HTTP-node SSRF allowlist pattern, M6's
construction nodes (which often consume vendor data), and the
existing `server/rapidly/integrations/` directory pattern
(`github/`, `stripe/`, `apple/`, `google/`, `microsoft/`, etc.).

## Scope decisions (locked)

- **MCP allowlist (not open URL).** Strategic plan §11/8 resolved:
  v1 ships an admin-managed allowlist of approved MCP server URLs
  per workspace. v2 may relax; v1 ships safer.
- **Reuse `httpx-oauth` for 3-legged OAuth.** Already in deps.
- **Vendor credentials live in `IntegrationCredential`** (M4.7). New
  credential `kind` values added per vendor.
- **Don't proxy file bytes through Rapidly.** Vendor file fetches go
  client-side (frontend asks Rapidly for a signed URL; Rapidly asks
  the vendor; signed URL is returned to the frontend, which fetches
  the bytes directly). Saves bandwidth + avoids storing other people's
  IP on our infra unnecessarily.

## Scope (5 PRs, ~3 weeks)

| # | Branch | What lands |
|---|---|---|
| 7.1 | `feat/integrations-framework` | Base connector class + sync-state tracking + per-workspace OAuth callback infra + connection-management UI |
| 7.2 | `feat/integration-autodesk-acc` | 3-legged OAuth; sheets / RFIs / model listing; nodes (list sheets, fetch model, post RFI) |
| 7.3 | `feat/integration-bentley-projectwise` | OAuth / token auth; document & model retrieval; nodes (list documents, fetch model) |
| 7.4 | `feat/integration-aconex` | OAuth; transmittals + document control; nodes (list transmittals, raise RFI to client) |
| 7.5 | `feat/integration-mcp-hosting` | Allowlist of MCP server URLs per workspace + bridge that exposes them as LLM tools in M4's LLM node |

Per-PR DoD in §6.

## Conventions

- All connectors live under `server/rapidly/integrations/<vendor>/` matching the existing pattern. Each has `client.py` (typed HTTP client wrapping the vendor API) + `oauth.py` (OAuth flow specifics) + `actions.py` + `types.py`. Construction nodes that wrap a connector live under `server/rapidly/agents/nodes/<vendor>_*.py`.
- All vendor secrets in `IntegrationCredential` rows; never in env vars per-workspace.
- All vendor HTTP calls go through the M4.3 HTTP node hardening (timeout cap, body size cap) when called from a workflow; out-of-band sync workers use the same caps.
- Each connector's OAuth callback hits a workspace-scoped URL: `/api/integrations/<vendor>/callback`. PKCE where the vendor supports it.
- No-attribution `scan` job runs every M7 PR. Vendor names appear in code and docs — that's fine; the only banned name is the agent-builder upstream's.

---

## 7.1 — Integration framework

Branch: `feat/integrations-framework`

### Goal

A reusable shape for vendor integrations so 7.2–7.4 differ only in
the vendor-specific quirks (auth, endpoints, payload shapes), not in
the infrastructure.

### Domain

```
server/rapidly/integrations/_base/
├── __init__.py
├── connector.py           # Connector[CredentialT, ClientT] base
├── sync_state.py          # tracks last-sync timestamps + cursors per (workspace, vendor, resource_kind)
├── oauth_callback.py      # generic callback handler dispatched by vendor
└── ratelimit.py           # per-(workspace, vendor) token-bucket so we don't blow vendor quotas
```

```python
# integrations/_base/connector.py
class Connector(Generic[CredentialPayloadT, ClientT], ABC):
    vendor_id: str                          # 'autodesk_acc', 'bentley_projectwise', 'aconex'
    credential_kind: IntegrationCredentialKind

    @abstractmethod
    async def authorize_url(self, workspace_id: UUID, redirect_uri: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> CredentialPayloadT: ...

    @abstractmethod
    async def refresh(self, payload: CredentialPayloadT) -> CredentialPayloadT: ...

    @abstractmethod
    def make_client(self, payload: CredentialPayloadT) -> ClientT: ...

    async def get_client(self, session: AsyncSession, workspace_id: UUID) -> ClientT:
        cred = await get_credential(session, workspace_id, self.credential_kind)
        payload = decrypt(cred.encrypted_payload)
        if is_expired(payload):
            payload = await self.refresh(payload)
            await store_credential(session, workspace_id, self.credential_kind, encrypt(payload))
        return self.make_client(payload)
```

### Sync state

```python
# models/integration_sync_state.py
class IntegrationSyncState(BaseEntity):
    __tablename__ = "integration_sync_states"
    workspace_id, vendor_id, resource_kind   # ('autodesk_acc', 'sheets')
    last_synced_at, last_cursor              # opaque per-vendor (page token, etag, modified_since stamp)
    error_message
```

### OAuth callback

`POST /api/integrations/{vendor_id}/callback?workspace_id=...` —
exchanges the code, encrypts the payload, stores as
`IntegrationCredential`, redirects back to the workspace's
settings page.

### Rate limit

Per-(workspace, vendor) token bucket in Redis. Defaults conservative
(1 req/s, burst 10). Tightenable per vendor since each has different
quota rules.

### Frontend

`/dashboard/[workspace]/settings/integrations/` — list of supported
vendors with **Connect** / **Disconnect** buttons. Connect opens the
vendor's OAuth consent in a popup; on return, the credential is
stored. Shows last-synced timestamps + error states.

### Routes

```
GET    /api/integrations                              list vendors + connection state
POST   /api/integrations/{vendor_id}/connect          returns authorize_url
GET    /api/integrations/{vendor_id}/callback         OAuth callback
DELETE /api/integrations/{vendor_id}                  disconnect (deletes credential)
GET    /api/integrations/{vendor_id}/sync-state       last sync info
```

### Tests

- Connector base: refresh path on expired credential; refresh failure path.
- OAuth callback exchanges code → encrypted credential persists; bad code → no credential persists.
- Sync state upsert.
- Rate limit reject after burst exhausted.

### Verify

```bash
cd server && uv run task test_fast && uv run task openapi_export
cd ../clients/apps/web && pnpm typecheck && pnpm test
```

---

## 7.2 — Autodesk ACC connector

Branch: `feat/integration-autodesk-acc`

### Vendor specifics

- **Auth:** 3-legged OAuth 2.0 via `developer.api.autodesk.com`. PKCE supported. Refresh tokens last 15 days.
- **API surfaces used in M7:** Sheets (`/construction/sheets/v1/`), RFIs (`/construction/rfis/v2/`), Model store (`/oss/v2/`).
- **Hub/project concepts:** Autodesk's "hub" maps to a customer org; "project" maps loosely to a project. Workspace setting picks the default hub.

### Connector

`server/rapidly/integrations/autodesk_acc/`:

```
autodesk_acc/
├── __init__.py
├── client.py           # AutodeskClient — get_hubs, list_projects, list_sheets, list_rfis, post_rfi, list_objects, get_object_download_url
├── oauth.py            # AutodeskConnector(Connector) — PKCE flow
└── types.py            # Pydantic models for the vendor payloads
```

### Nodes

```
server/rapidly/agents/nodes/autodesk_list_sheets.py
server/rapidly/agents/nodes/autodesk_fetch_model.py    # returns signed URL, not bytes
server/rapidly/agents/nodes/autodesk_post_rfi.py
server/rapidly/agents/nodes/autodesk_list_rfis.py
```

`autodesk_fetch_model.py` returns a signed URL pointing at Autodesk;
the workflow either passes the URL to a downstream HTTP node or
hands it to the user. Bytes don't transit Rapidly. If a workflow
needs the bytes (e.g., to ingest into the M3 viewer), it explicitly
chains a "fetch URL" node and a "register as federated model" node —
the explicit chain makes the data-transit decision auditable.

### Frontend

Vendor card in the Integrations settings page. On connect, opens a
popup to Autodesk's consent screen. After success: shows the linked
hub picker.

### Tests

- OAuth callback against a recorded vendor response (vcrpy fixture).
- Each node against mocked client; assert correct endpoint shape.
- Signed-URL pass-through: assert the node returns the URL, not bytes.

### Verify

Manual (requires real Autodesk dev account): connect, list sheets
for a real project, post an RFI, see it appear in ACC.

---

## 7.3 — Bentley ProjectWise connector

Branch: `feat/integration-bentley-projectwise`

### Vendor specifics

- **Auth:** Bentley CONNECT — OIDC + OAuth 2.0 against `ims.bentley.com`. PKCE supported.
- **API:** ProjectWise design integration service (REST). Documents + folders + model references.
- **iModel vs ProjectWise:** Two distinct Bentley products. M7.3 covers ProjectWise document control. iModelHub (model hosting) is a v2 add if user demand surfaces.

### Connector

`server/rapidly/integrations/bentley_projectwise/`:

```
bentley_projectwise/
├── client.py           # list_folders, list_documents, get_document_metadata, get_document_download_url
├── oauth.py
└── types.py
```

### Nodes

```
server/rapidly/agents/nodes/projectwise_list_documents.py
server/rapidly/agents/nodes/projectwise_fetch_document.py     # signed URL
server/rapidly/agents/nodes/projectwise_search.py             # full-text search
```

### Tests + Verify

Same pattern as 7.2. VCR-recorded fixtures for the connector.

---

## 7.4 — Aconex connector

Branch: `feat/integration-aconex`

### Vendor specifics

- **Auth:** Aconex API uses HTTP Basic over HTTPS (no OAuth as of 2026 — confirm at implementation time; if they've added OAuth, prefer it). Credentials are a project-scoped API username + password.
- **Surfaces:** Documents (`/api/projects/{id}/documents`), Transmittals (`/api/projects/{id}/transmittals`), Mail (which Aconex calls "Mail" but is essentially the RFI surface).

### Connector

`server/rapidly/integrations/aconex/`:

```
aconex/
├── client.py
├── auth.py             # Basic auth (or OAuth if they've added it); credential payload is {username, password_encrypted}
└── types.py
```

### Nodes

```
server/rapidly/agents/nodes/aconex_list_transmittals.py
server/rapidly/agents/nodes/aconex_create_transmittal.py
server/rapidly/agents/nodes/aconex_raise_mail.py          # the Aconex equivalent of an RFI to the client
```

### Credential storage

For Basic-auth flow: credential payload is `{username, password}`
both encrypted. Rotation flow on the integrations page (user
reenters password, re-encrypts).

### Tests + Verify

Same pattern as 7.2 + 7.3.

---

## 7.5 — MCP hosting

Branch: `feat/integration-mcp-hosting`

### Goal

Workspace admins can add approved MCP server URLs to an allowlist.
M4's LLM node grows an `mcp_servers: list[str]` config — workflow
authors pick servers from the allowlist; the node exposes their tools
to the LLM call.

Per strategic plan §11/8: **allowlist, not arbitrary URLs.** A
workflow that calls an arbitrary MCP server is a tool-supply-chain
risk. The admin curates trusted servers; everyone else picks from
that list.

### Domain

```
server/rapidly/integrations/mcp/
├── allowlist.py        # CRUD on the per-workspace server allowlist
├── bridge.py           # boots a Python MCP client, lists tools, executes tool calls inside LLM-node context
└── types.py
```

```python
# models/mcp_server.py
class McpServer(BaseEntity, SoftDeleteMixin):
    __tablename__ = "mcp_servers"
    workspace_id, name, transport ('stdio' | 'http' | 'sse')
    url_or_command: Mapped[str]              # https URL for http/sse; shell command for stdio (gated to admin)
    auth_kind ('none' | 'bearer' | 'oauth')
    credential_id (FK to IntegrationCredential, nullable)
    added_by_id, added_at
```

### LLM-node integration

The `LLM call` node from M4.4 gets a new optional config field:

```python
"mcp_server_ids": list[str],
```

When set, the node:

1. Looks up each McpServer.
2. Boots an MCP client per server (using the `mcp` Python package — add to deps).
3. Aggregates the tools the servers expose.
4. Passes them to the pydantic-ai Agent as tools.
5. The LLM call may invoke them; each tool call is logged as a sub-event under the NodeRun's trace.

### Frontend

Workspace settings page: `/dashboard/[workspace]/settings/mcp-servers/`.
Admin-only. Add server form with transport / URL / auth fields. Lists
existing servers with last-used timestamps.

In the LLM node's config panel (M5.3): a new multi-select picker
sourced from the workspace's McpServer allowlist.

### Security

- **stdio transport disabled by default** at the workspace level — it executes a shell command, which means full process access. Behind a workspace setting `mcp_allow_stdio` that defaults `false`. If enabled, the command is run inside the M4.5 code-sandbox (subprocess+seccomp+rlimit) so a malicious MCP server can't pivot into the host.
- **http/sse transport** is rate-limited per the M7.1 token-bucket and goes through the M4.3 HTTP-node SSRF allowlist (the MCP server's hostname must be in the workspace's outbound allowlist or be explicitly allowed for MCP).
- **Tool-call payloads logged** but redacted at the secret boundary (we don't log the actual tool arguments by default; opt-in per-server).

### Tests

- McpServer CRUD with admin gating.
- Bridge: boot, list tools, execute, shut down — for each transport.
- LLM node with mcp_server_ids: tool call shows up in NodeRun trace as a sub-event.
- stdio sandbox: an MCP server that tries `socket()` fails (seccomp).
- Disallowed-stdio rejection when workspace flag is off.

### Verify

Manual: spin up a local MCP server (e.g., the official filesystem
server), add to workspace allowlist over a localhost URL (admin-only
setting for development), wire into an LLM node, watch the LLM make
a tool call.

---

## 6. Per-PR Definition of Done (M7 flavor)

```markdown
## Definition of Done — M7 integration

### Surface added
- Connector / nodes / settings: <names>
- New deps: <package@version or none>
- Migrations: <names>
- Credential kind(s): <list>

### Verification
- [ ] `uv run task lint && lint_types && test_fast && openapi_export` green
- [ ] `pnpm typecheck && pnpm lint && pnpm test` green
- [ ] No-attribution `scan` job green
- [ ] VCR-recorded fixtures for vendor calls; no live calls in CI
- [ ] Manual: OAuth flow completes against the real vendor

### Security
- [ ] Credentials encrypted at rest via existing fernet stack
- [ ] No vendor secret logged
- [ ] Outbound HTTP respects M4.3 SSRF allowlist
- [ ] Rate-limit token bucket enforced
- [ ] File bytes flow client-direct via signed URLs, not through Rapidly (except where the workflow explicitly chains a "fetch URL" node)

### Vendor quirks documented
- [ ] OAuth specifics (PKCE? refresh-token lifetime? token endpoint url?)
- [ ] Quota notes (vendor's stated limits + our chosen bucket size)
- [ ] Known gaps (e.g., "iModelHub not supported in v1")
```

---

## 7. Acceptance for M7 as a whole

After 7.1–7.5 land:

- [ ] **Integrations framework live.** Settings page lists vendors; OAuth callbacks work; sync state persisted.
- [ ] **Three vendors connectable.** Real-OAuth tested for Autodesk + Bentley; basic-auth tested for Aconex.
- [ ] **Vendor-named nodes available** in M5.3's palette under a new "Vendor" category.
- [ ] **MCP allowlist + LLM-node integration** — admin adds a server; workflow author picks it; LLM tool call traces correctly.
- [ ] **No-attribution `scan` job green** on every M7 PR.
- [ ] **No vendor secrets in code/env** — every credential resolved at runtime from `IntegrationCredential`.
- [ ] **Memory updated.** `project_m7_integrations_complete.md` written. Pivot memory's "model viewers/IFC tooling self-hosted" line continues; new note about vendor connectors being workspace-opt-in.

---

## 8. Rollback

Each M7 PR is its own commit on main.

- 7.1: revert + `downgrade()` drops `integration_sync_states`. Existing IntegrationCredentials remain (those came from M4.7).
- 7.2: revert; nodes + connector + frontend card disappear. Existing Autodesk credentials remain in DB but unused.
- 7.3, 7.4: same shape as 7.2.
- 7.5: revert + `downgrade()` drops `mcp_servers`. The `mcp` package stays in lockfile.

---

## 9. After M7

`MEMORY.md` updates:

- Add `[M7 integrations complete (YYYY-MM-DD)](project_m7_integrations_complete.md)`. Body: lists Autodesk ACC + Bentley ProjectWise + Aconex + MCP hosting, notes the allowlist-only MCP policy.
- Update the pivot memory: append "Vendor connectors live in 7.x; all opt-in per workspace; file bytes flow client-direct via signed URLs."

Next milestone: **M8 — Mobile + polish (2 weeks).** Tablet PWA per
strategic plan §11/6 (iPad Safari + Android Chrome; phone read-only).
Field-engineer use cases: open a markup board on a tablet, photograph
a site condition, trigger a site-walk workflow from the upload. Plan
in `M8_EXECUTION.md` on user go-ahead.

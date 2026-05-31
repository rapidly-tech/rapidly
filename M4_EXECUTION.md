# M4 — Agent runtime (backend)

Executable plan for milestone M4 of `RAPIDLY_ENGINEERING_SUITE_PLAN.md`.
M4 builds the **backend** of the Agents chamber: domain model, node
catalog, execution engine, evals, RAG, credential store. M5 (separate
plan) ships the frontend graph editor.

**Read M0 + M1 + M2 + M3 first.** M4 assumes the no-attribution gate
is live (M0), the demolition has happened (M1), the markup primitives
exist (M2), and the 3D viewer is up (M3). Of those, only M0 is a hard
prerequisite — M4 doesn't touch markup, viewer, or demolished surfaces.

## Hard rule for M4

Every line of agent-runtime code is a **clean-room rewrite**. The
architecture below is informed by reading the public design docs of a
similar open-source product; **no upstream source has been opened
during implementation**. Per the clean-room policy memory and the
no-attribution rule-doc memory (both under the project's auto-memory
directory, outside the repo). The no-attribution `scan` gate runs
on every M4 PR; if it ever turns red, fix the leak, don't bypass.

If anything in this plan reads like it could have come from an
upstream's class layout, **rewrite**. Use our own conventions: plain
async functions, our `actions.py` / `queries.py` split, our
`Repository[Model]` base, our `Authenticator` dependency, our
Dramatiq actor pattern. Variable names and module structure come
from how *we* organize backend domains, not how they do.

## Scope (8 PRs, ~4 weeks)

| # | Branch | What | Migration? |
|---|---|---|---|
| 4.1 | `feat/agents-domain-scaffold` | `server/rapidly/agents/` + ORM (Workflow / WorkflowVersion / Run / NodeRun) + CRUD routes; no execution | yes |
| 4.2 | `feat/agents-execution-engine` | Dramatiq actor; topological walk; state machine; "echo" node only | none |
| 4.3 | `feat/agents-deterministic-nodes` | HTTP, branch, loop, file read/write (the deterministic, low-risk nodes) | none |
| 4.4 | `feat/agents-llm-nodes` | LLM + structured-output nodes; pydantic-ai backend; Anthropic + Google extras | none |
| 4.5 | `feat/agents-code-node-sandbox` | Code node; subprocess+seccomp sandbox (security-critical) | none |
| 4.6 | `feat/agents-rag` | pgvector extension; VectorCollection + Document indexing; RAG-search node | yes |
| 4.7 | `feat/agents-credential-and-coordination` | IntegrationCredential (encrypted); human-in-loop node; sub-workflow node | yes |
| 4.8 | `feat/agents-dataset-and-eval` | Dataset / DatasetRow / EvalRun; eval runner | yes |

Each PR ships its own tests + stamps the per-PR DoD (§7).

## Conventions

- Backend module convention is mandatory (`server/CLAUDE.md`): `api.py` / `actions.py` / `queries.py` / `types.py` / `permissions.py` / `workers.py` / `ordering.py`.
- All queries go through `Repository[Model]`. Never query the DB directly in `actions.py` or `api.py`.
- All M4 work lives under `server/rapidly/agents/` — one new domain at the top level.
- Pre-push: `cd server && uv run task lint && uv run task lint_types && uv run task test_fast && uv run task openapi_export`.
- Pre-push frontend: `cd clients && pnpm typecheck` — even though M4 is backend, the OpenAPI client regenerates and any drift surfaces.
- Per-PR DoD in §7.

---

## 4.1 — Domain scaffold

Branch: `feat/agents-domain-scaffold`

### Goal

Create the `server/rapidly/agents/` domain with submodules, ORM rows,
and CRUD routes. No execution yet — clicking "Run" returns
`501 Not Implemented`. Backend exists for M5's UI to bind against.

### Module layout

```
server/rapidly/agents/
├── __init__.py
├── permissions.py            # workspace-scoped Authenticator deps
├── workflow/
│   ├── __init__.py
│   ├── api.py
│   ├── actions.py
│   ├── queries.py
│   ├── types.py
│   └── ordering.py
├── workflow_version/         # same shape; immutable snapshots
├── run/
└── node_run/
```

Submodule split rationale: workflows are mutable; versions are
append-only snapshots of the graph_json at a moment in time;
runs are immutable execution records; node_runs are immutable
per-step records. Splitting these into four modules keeps each
queries.py file small (~150 LOC) and makes the auth contract
per-entity explicit (workflows are writable by project members;
runs are read-only after they finish; node_runs are read-only
period).

### ORM rows

`server/rapidly/models/`:

```python
# models/workflow.py
class Workflow(BaseEntity, SoftDeleteMixin):
    __tablename__ = "workflows"
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="cascade"))
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    current_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflow_versions.id"), nullable=True)
    archived_at: Mapped[datetime | None]

# models/workflow_version.py
class WorkflowVersion(BaseEntity):
    __tablename__ = "workflow_versions"
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id", ondelete="cascade"))
    version_number: Mapped[int]
    graph_json: Mapped[dict] = mapped_column(JSONB)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("workflow_id", "version_number"),)

# models/run.py
class Run(BaseEntity):
    __tablename__ = "agent_runs"
    workflow_version_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_versions.id"))
    triggered_by_kind: Mapped[TriggeredByKind]  # 'user', 'webhook', 'schedule', 'sub_workflow'
    triggered_by_id: Mapped[UUID | None]
    status: Mapped[RunStatus]  # 'pending', 'running', 'succeeded', 'failed', 'cancelled', 'awaiting_human'
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    error_message: Mapped[str | None] = mapped_column(Text)
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data: Mapped[dict] = mapped_column(JSONB, default=dict)

# models/node_run.py
class NodeRun(BaseEntity):
    __tablename__ = "agent_node_runs"
    run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="cascade"))
    node_id: Mapped[str] = mapped_column(String(64))    # graph-local id from graph_json
    node_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[NodeRunStatus]  # 'pending', 'running', 'succeeded', 'failed', 'skipped', 'awaiting_human'
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    error_message: Mapped[str | None] = mapped_column(Text)
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    parent_node_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_node_runs.id"))  # for loop iterations / branches
```

### Routes

```
# Workflows
POST   /api/workflows                          create
GET    /api/workflows                          list (paginated, filterable by project_id / archived)
GET    /api/workflows/{id}                     get
PATCH  /api/workflows/{id}                     update name/description/archived_at
DELETE /api/workflows/{id}                     soft delete

# Versions (append-only snapshots)
POST   /api/workflows/{id}/versions            new version (publishes graph_json; bumps current_version_id)
GET    /api/workflows/{id}/versions            list
GET    /api/workflows/{id}/versions/{vid}      get one

# Runs
POST   /api/workflows/{id}/runs                start a run (501 in M4.1; wires up in M4.2)
GET    /api/runs                               list (paginated, filterable by workflow_id, status, time range)
GET    /api/runs/{id}                          get one + node_runs
POST   /api/runs/{id}/cancel                   cancel (501 in M4.1)
```

### Scopes

Add to `identity/auth/scope.py`:

```
workflows_read     # list/get workflows + versions + runs
workflows_write    # create/update/archive workflows + new versions
runs_trigger       # start runs (separate from workflows_write because
                   # operators may grant API-key runs without granting
                   # full edit rights)
```

### Migration

```bash
cd server
uv run alembic revision -m "agents: workflow, workflow_version, run, node_run tables"
```

### Tests

- Per-submodule action tests: CRUD, role gating, soft delete (workflow only).
- Per-submodule route tests: 401 anonymous, 200 authenticated.
- Versioning invariant: creating a version bumps `current_version_id`; old versions remain accessible.

### Verify

```bash
cd server
uv run task test_fast
uv run task openapi_export
cd ../clients/packages/client && pnpm generate && cd ../../apps/web && pnpm typecheck
# expected: new types generated, no breaking changes to existing client
```

---

## 4.2 — Execution engine

Branch: `feat/agents-execution-engine`

### Goal

Make `POST /api/workflows/{id}/runs` actually run something. The
engine walks the graph topologically, executes node bodies, persists
`NodeRun` rows, and streams trace events through
`analytics/eventstream`. Node catalog is **echo only** in this PR
(input → output unchanged) — exists to prove the engine works.
Real nodes ship in 4.3–4.7.

### Architecture

`server/rapidly/agents/execution/`:

```
execution/
├── __init__.py
├── actions.py          # public surface: start_run, cancel_run, on_run_completed
├── engine.py           # topological walk + per-node dispatch
├── node_registry.py    # maps node_type string → NodeHandler (Protocol)
├── state.py            # state machine: pending→running→succeeded/failed/cancelled/awaiting_human
├── workers.py          # Dramatiq actor that owns a Run from start to finish
└── trace.py            # emit events into analytics/eventstream
```

### Engine semantics

- One Dramatiq actor per `Run`. The actor walks the DAG synchronously inside its own process; per-node concurrency is handled with `asyncio.gather` over independent branches.
- **Why one actor per Run, not per Node:** simplifies state (the Run is owned by exactly one worker at a time), simplifies cancellation (kill the actor → run is dead), simplifies trace ordering (sequential within an actor). The cost — one slow LLM call blocks the actor's other branches — is acceptable for v1; v2 can split if needed.
- Sub-workflow node (lands in 4.7) spawns a child actor for the sub-run.
- Loop node (lands in 4.3) iterates inside the actor; each iteration creates a `NodeRun` with `parent_node_run_id` set.
- Awaiting-human nodes (lands in 4.7) park the run state and exit the actor; a resume event re-enqueues a new actor that picks up from the parked state.

### Node handler contract

```python
# execution/node_registry.py
class NodeHandler(Protocol):
    node_type: str

    async def execute(
        self,
        ctx: NodeExecutionContext,
        input_data: dict[str, Any],
        node_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Pure function: input + config → output. No side effects on
        the Run row; the engine owns persistence."""
```

Handlers are registered in `node_registry.py` at module load. Adding
a node = adding a file in `agents/nodes/<type>.py` that defines a
handler and gets imported once.

### Trace events

Each node start/finish/error emits an event via
`analytics/eventstream`:

```
event_type:  agent.node.started | agent.node.completed | agent.node.failed
payload:     { run_id, node_run_id, node_id, node_type, ... }
```

UI consumers subscribe via the existing SSE infrastructure.

### Cancellation

`POST /api/runs/{id}/cancel`:

1. Set `Run.status = 'cancelled'` via optimistic concurrency check.
2. Publish a `run.cancelled` message on Redis pubsub; the actor polls
   this every ~100 ms between node calls and exits cleanly on receipt.

### Tests

- Engine unit tests: topological walk with diamond graph, with a cycle (must reject), with multiple disconnected components (runs each).
- State machine tests: every legal transition; every illegal transition rejected.
- Echo-node test: in/out round-trip.
- Cancellation test: start a run, cancel mid-execution, confirm status and that no further `NodeRun` rows appear.

### Verify

Same as 4.1 plus:

```bash
# Manual: POST a workflow with two echo nodes wired in series.
# Trigger a run. Confirm status moves pending→running→succeeded
# and both NodeRun rows show input==output.
```

---

## 4.3 — Deterministic nodes (HTTP, branch, loop, file read/write)

Branch: `feat/agents-deterministic-nodes`

### Nodes

```
agents/nodes/
├── http.py        # GET/POST/etc; headers, body, timeout; returns {status, body, headers}
├── branch.py      # condition expression (CEL? jsonata? — pick one, see below) → routes input to one of N outputs
├── loop.py        # iterates over input list, runs body subgraph; aggregates
├── file_read.py   # reads from catalog/file by document_id; returns {bytes_b64, mime, name}
└── file_write.py  # writes bytes to MinIO via catalog/file; returns {document_id}
```

### Expression language for `branch`

Options:
- **CEL** (Google Common Expression Language) via `cel-python`. Familiar, sandboxed, well-spec'd.
- **jsonata** via `jsonata-python`. JSON-native, slightly weirder syntax for engineers.
- **Custom mini-DSL.** Don't.

Recommend **CEL**. Reasons: spec'd grammar, sandbox-safe, no Python eval, integrates with structured outputs cleanly. Adds `cel-python` to backend deps.

### HTTP node hardening

- **Domain allowlist (workspace-scoped).** Reuse the workspace settings shape; default-deny outbound. Reason: a workflow that calls arbitrary URLs is an SSRF vector against the internal network. Enforce in `http.py` before issuing the request.
- **Timeout cap.** 30s hard ceiling; configurable down per call.
- **No redirect-follow by default.** Off; can be opted in per call (and is then capped at 3 hops).
- **Request body size cap.** 10 MB. Response body cap 50 MB; larger → fail with `body_too_large`.

### File read/write

Reuses the existing `catalog/file/` path. No new tables. ACL: the
calling workflow's workspace must own the document; cross-workspace
reads fail with `not_permitted`.

### Tests

- HTTP node: mock the allowlist via fixture; assert disallowed-domain rejection, redirect cap, timeout, body cap.
- Branch node: each CEL operator; missing-variable handling; type-mismatch.
- Loop node: empty iterable, iteration error, cancellation mid-loop.
- File read/write: round-trip a small blob; cross-workspace ACL denial.

### Verify

```bash
cd server && uv run task test_fast && uv run task openapi_export
```

Manual: build a workflow that fetches a URL, branches on response status, loops over a list of strings, writes a result file. Trigger. Inspect `NodeRun` rows for the full trace.

---

## 4.4 — LLM + structured-output nodes

Branch: `feat/agents-llm-nodes`

### Goal

Two nodes: a generic LLM call, and a structured-output call (LLM
with a target JSON schema). pydantic-ai is the backend abstraction;
the frontend's `@ai-sdk/*` is unrelated to this PR (M5 territory).

### Backend deps

```bash
cd server
uv add 'pydantic-ai-slim[anthropic,google]'
```

We already have `[openai]`. After this: Anthropic, Google, OpenAI,
and Ollama (the last via the OpenAI-compatible endpoint).

### Provider routing

`agents/nodes/llm.py`:

```python
async def execute(self, ctx, input_data, node_config):
    provider = node_config["provider"]    # 'anthropic' | 'openai' | 'google' | 'ollama'
    model    = node_config["model"]
    prompt   = render_prompt(input_data, node_config["prompt_template"])
    temp     = node_config.get("temperature", 0.7)

    agent = pydantic_ai.Agent(f"{provider}:{model}", system_prompt=node_config.get("system_prompt", ""))
    result = await agent.run(prompt, model_settings={"temperature": temp})
    return {"text": result.output, "usage": {"input_tokens": ..., "output_tokens": ...}}
```

Credentials come from `IntegrationCredential` (which lands in 4.7).
For 4.4 — read keys from workspace settings as a stopgap; 4.7 will
swap to the encrypted credential store.

### Structured output

`agents/nodes/structured_output.py`:

```python
async def execute(self, ctx, input_data, node_config):
    schema = node_config["schema_json"]       # JSON Schema
    Target = json_schema_to_pydantic_model(schema)
    agent = pydantic_ai.Agent(model, output_type=Target)
    result = await agent.run(input_data["text"])
    return {"data": result.output.model_dump()}
```

`json_schema_to_pydantic_model` is a small utility; v1 supports
objects/arrays/primitives, no $ref. Defer $ref to v2.

### Usage metering

Every LLM call writes a usage row that the billing module reads to
compute per-workspace cost. Reuses the existing
`analytics/event` infrastructure; new event type `agent.llm.usage`
with payload `{provider, model, input_tokens, output_tokens, cost_usd}`.

### Tests

- LLM node test against a stubbed provider (pydantic-ai's `TestModel`).
- Structured-output test for each primitive + nested object + array.
- Usage metering: confirms an event row lands after each call.
- Cost computation: input_tokens × per-1k-rate matches the recorded `cost_usd`.

### Verify

Manual: build a workflow with an LLM node that draws structured RFI fields out of free-form text. Confirm the output validates against the schema.

---

## 4.5 — Code node + sandbox

Branch: `feat/agents-code-node-sandbox`

### Goal

Run untrusted Python (workflow author's, who is workspace-internal
but still untrusted relative to the API process) without letting it
break out.

### Sandbox choice (strategic plan open decision §11/7)

Per strategic plan recommendation: **subprocess + seccomp** for v1.
gVisor in M9 if real isolation matters. Trade-off:

- **subprocess+seccomp:** ships with Linux; we configure a seccomp filter that allows read/write/futex/etc. but blocks `execve`, `socket`, `open` outside a whitelisted directory, etc. Good enough against accidental damage; not airtight against a determined attacker who knows the filter.
- **gVisor:** real user-mode kernel sandbox. Much stronger; adds a runtime dep and ~50 ms per call latency. Defer.

### Implementation

`agents/nodes/code.py`:

1. Write the user's source to a temp file inside a per-call tempdir.
2. Write the input_data as JSON to `input.json` in the tempdir.
3. `subprocess.Popen(["python", "runner.py"], preexec_fn=apply_seccomp, ...)`
   where `runner.py` is a tiny harness that:
   - reads `input.json`
   - imports the user module as `user_code`
   - calls `user_code.handler(input)`
   - writes the return value as JSON to `output.json`
4. Wait with a configurable timeout (default 30s, cap 5min).
5. Read `output.json` → return.
6. Tempdir cleanup is unconditional (try/finally).

### Seccomp filter

`agents/nodes/_seccomp.py`:

```python
ALLOWED_SYSCALLS = {"read", "write", "futex", "mmap", "munmap", "brk", ...}
def apply_seccomp():
    # use libseccomp-python
    f = SyscallFilter(defaction=KILL)
    for name in ALLOWED_SYSCALLS:
        f.add_rule(ALLOW, name)
    f.load()
```

Run a real audit of `pydantic` + the stdlib's import-time syscalls
before deciding the allowlist. Strict enough to reject network +
file outside tempdir; loose enough that JSON parsing works.

### Resource limits

`setrlimit` before exec:
- RLIMIT_AS: 512 MB
- RLIMIT_CPU: 30 s
- RLIMIT_NOFILE: 32
- RLIMIT_NPROC: 1 (no forks)

### Tests

- Allowed code returns expected output.
- `open("/etc/passwd")` fails — seccomp kills the process.
- Network attempt (`socket.socket()`) fails.
- Infinite loop hits CPU limit, returns timeout error.
- Memory bomb hits RLIMIT_AS, returns oom error.
- Tempdir cleanup happens on success, on failure, on timeout.

### Verify

Manual: code node with `def handler(input): return {"doubled": input["x"] * 2}`. Run; expect `{"doubled": 84}` for input `{"x": 42}`. Then code node with `import socket; socket.socket()`. Expect failure with `seccomp: SIGSYS`.

### Risk

This is the only M4 PR where a security bug = remote code execution. **Get a second pair of eyes before merging**, ideally someone who has written Linux sandbox code. If unavailable, gate this node behind a workspace feature flag default-off until the audit happens.

---

## 4.6 — RAG (pgvector + vector collection + indexing)

Branch: `feat/agents-rag`

### Backend deps

```bash
cd server
uv add pgvector
```

Postgres extension activation:

```python
# migration
op.execute("CREATE EXTENSION IF NOT EXISTS vector")
```

`pgvector` is widely supported on managed Postgres; on Hetzner self-host
the extension package needs to be installed in the container image.
Update `server/docker-compose.yml` Postgres image to one that bundles
the extension (e.g., `pgvector/pgvector:pg16`).

### Domain

```
agents/vector_collection/
├── api.py / actions.py / queries.py / types.py / permissions.py / workers.py
agents/nodes/rag_search.py
```

```python
# models/vector_collection.py
class VectorCollection(BaseEntity, SoftDeleteMixin):
    __tablename__ = "vector_collections"
    workspace_id, project_id (nullable), name
    embedding_model: Mapped[str]  # e.g., 'text-embedding-3-small'
    dimensions: Mapped[int]       # set at create time, immutable

# models/vector_chunk.py
class VectorChunk(BaseEntity):
    __tablename__ = "vector_chunks"
    collection_id, source_document_id (nullable for raw inserts),
    chunk_index, text, metadata: dict
    embedding: Mapped[Vector] = mapped_column(Vector(dim))  # pgvector type
```

Index: `CREATE INDEX ON vector_chunks USING hnsw (embedding vector_cosine_ops)`.

### Indexing pipeline

`agents/vector_collection/workers.py`:

```python
@actor(actor_name="rag.ingest_document", priority=TaskPriority.LOW)
async def ingest_document(collection_id: UUID, document_id: UUID) -> None:
    # 1) Fetch the document bytes (catalog/file).
    # 2) Detect mime; chunk:
    #    - PDF: pdfplumber, per-page
    #    - Markdown / text: by paragraph w/ overlap
    #    - DOCX: python-docx, by paragraph
    #    - Other: skip with warning event
    # 3) Embed batch (configurable provider; default OpenAI text-embedding-3-small)
    # 4) Insert VectorChunk rows in batches of 100.
```

### RAG search node

`agents/nodes/rag_search.py`:

```python
async def execute(self, ctx, input_data, node_config):
    collection = await get_collection(ctx.session, node_config["collection_id"])
    query_embedding = await embed_text(input_data["query"], collection.embedding_model)
    chunks = await search_top_k(ctx.session, collection.id, query_embedding, k=node_config.get("k", 5))
    return {"results": [{"text": c.text, "score": c.score, "metadata": c.metadata} for c in chunks]}
```

### Tests

- VectorChunk insert + query round-trip with a tiny embedding.
- Dimension-mismatch insert → reject.
- HNSW recall test against a known dataset (~95% recall @ k=10).
- Indexing pipeline: PDF chunk count matches page count (sample fixture).

### Verify

Manual: create a collection, index 3 PDFs, run a RAG search via the node from a workflow, confirm relevant chunks come back.

---

## 4.7 — Credential store + human-in-loop + sub-workflow

Branch: `feat/agents-credential-and-coordination`

Three small additions that unblock the rest of the catalog.

### IntegrationCredential

`agents/credential/`:

```python
# models/integration_credential.py
class IntegrationCredential(BaseEntity, SoftDeleteMixin):
    __tablename__ = "integration_credentials"
    workspace_id, name, kind  # 'http_bearer', 'openai_api_key', 'github_oauth', ...
    encrypted_payload: Mapped[bytes]  # fernet via existing crypto module
    created_by_id
```

Routes: standard CRUD + a `reveal` endpoint that returns the
decrypted payload **only** to a worker context (the Dramatiq actor),
never to a UI request. Enforced by checking the request's
`source` header (worker-only path) + a separate scope.

Reuses `server/rapidly/core/crypto.py` (or wherever the Fernet key
lives — confirm during implementation).

### Backfill 4.4

The LLM nodes from 4.4 read their API keys from workspace settings.
In this PR, swap to `IntegrationCredential` lookup. Migration adds a
default credential per existing workspace by copying the current
setting value. Schedule a follow-up PR to delete the old setting
column after a deprecation window.

### Human-in-loop node

`agents/nodes/human_in_loop.py`:

```python
async def execute(self, ctx, input_data, node_config):
    # 1) Create a notification (existing messaging/notification) addressed
    #    to node_config["recipient_user_id"] with prompt + schema.
    # 2) Mark this NodeRun status='awaiting_human'.
    # 3) Mark the parent Run status='awaiting_human'.
    # 4) Raise AwaitingHumanInterrupt — engine catches it, persists state, exits actor.
```

When the human responds (a new endpoint
`POST /api/runs/{id}/nodes/{nid}/respond`):

- Validates response against `node_config["response_schema"]`.
- Marks NodeRun.status='succeeded', writes output_data = response.
- Marks Run.status='running' again.
- Enqueues a resumption actor that picks up the DAG walk from the node's downstream neighbors.

### Sub-workflow node

`agents/nodes/sub_workflow.py`:

```python
async def execute(self, ctx, input_data, node_config):
    sub_workflow_id = node_config["workflow_id"]
    pin_version = node_config.get("version_id")  # optional; default to current_version_id
    sub_run = await create_run(
        ctx.session,
        workflow_version_id=pin_version or get_current_version(sub_workflow_id),
        input_data=input_data,
        triggered_by_kind='sub_workflow',
        triggered_by_id=ctx.run_id,
    )
    # Block until sub_run terminal state. Stream sub_run trace events
    # into parent run's trace stream with a "parent_node_run_id" tag.
    while True:
        sub_run = await get_run(ctx.session, sub_run.id)
        if sub_run.status in TERMINAL_STATES:
            break
        await asyncio.sleep(0.5)
    if sub_run.status == 'succeeded':
        return sub_run.output_data
    raise SubWorkflowFailed(sub_run.id, sub_run.error_message)
```

Recursion guard: count parent-chain depth; reject if > 10. Prevents
runaway recursion bombs.

### Tests

- Credential encrypt/decrypt round-trip; the API never returns plaintext to a UI request.
- Human-in-loop: pause, respond, resume; respond with bad schema → 400.
- Sub-workflow happy path; sub-workflow failure surfaces error to parent; recursion-guard kicks in at depth 11.

---

## 4.8 — Dataset + eval

Branch: `feat/agents-dataset-and-eval`

### Goal

Workflow authors can store test datasets and run a workflow against
them, producing metric results.

### Domain

```
agents/dataset/  + agents/eval/
```

```python
# models/dataset.py
class Dataset(BaseEntity, SoftDeleteMixin):
    __tablename__ = "agent_datasets"
    workspace_id, project_id (nullable), name
    schema_json: Mapped[dict] = mapped_column(JSONB)  # input + expected_output shapes

# models/dataset_row.py
class DatasetRow(BaseEntity):
    __tablename__ = "agent_dataset_rows"
    dataset_id, row_index
    data: Mapped[dict] = mapped_column(JSONB)
    expected_output: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("dataset_id", "row_index"),)

# models/eval_run.py
class EvalRun(BaseEntity):
    __tablename__ = "agent_eval_runs"
    workflow_version_id, dataset_id
    status: pending / running / completed / failed
    metric_results: Mapped[dict] = mapped_column(JSONB)
    per_row_results: Mapped[list[dict]] = mapped_column(JSONB)  # row_index, output, score, ...
    started_at, completed_at
```

### Eval runner

`agents/eval/workers.py`:

```python
@actor(actor_name="agents.run_eval", priority=TaskPriority.LOW)
async def run_eval(eval_run_id: UUID) -> None:
    # 1) Load EvalRun, dataset, workflow_version.
    # 2) For each DatasetRow:
    #    - Start a child Run with row.data as input.
    #    - Wait for terminal status.
    #    - Score the output vs row.expected_output (default scorer = exact-match
    #      on a configurable JSON path; LLM-as-judge scorer is a stretch goal).
    # 3) Aggregate metrics: pass_rate, avg_latency_ms, total_cost_usd.
    # 4) Update EvalRun row.
```

Concurrency: cap at 10 child runs in flight. Sequence the rest.

### Metrics

v1 metrics:

- `pass_rate` — proportion of rows whose output matches the expected (exact-match JSON-path scorer)
- `avg_latency_ms` — mean per-row run duration
- `total_cost_usd` — sum of `agent.llm.usage` events for the eval's child runs

LLM-as-judge scorer is a v2 add — defer.

### Tests

- Dataset CRUD.
- Eval runner: small dataset (3 rows), all-pass case, mixed-pass case, all-fail case.
- Latency + cost aggregation.

### Verify

Manual: import a tiny CSV as a dataset (3 rows), run an eval, inspect `metric_results` and the per-row breakdown.

---

## 5. Acceptance for M4 as a whole

After 4.1–4.8 land:

- [ ] **`server/rapidly/agents/` exists** with all 8+ submodules.
- [ ] **All M4 PRs landed the no-attribution `scan` job green** — every single one.
- [ ] **OpenAPI client regenerated** at each PR; no drift on the dashboard typecheck.
- [ ] **End-to-end workflow runs.** Create a workflow with: trigger → HTTP fetch → LLM extract → structured output → file write → end. Trigger it. Inspect Run + NodeRun rows + trace events.
- [ ] **RAG end-to-end.** Index a few PDFs, query the collection from a workflow.
- [ ] **Code-sandbox security tests pass.** All five red-team tests in §4.5 fail (correctly) for malicious code.
- [ ] **Eval runner produces metrics** on a small dataset.
- [ ] **Memory updated.** `project_m4_agent_runtime_complete.md` written. Pivot memory's Agents-chamber line annotated `[BACKEND LANDED 2026-MM-DD; UI is M5]`.

---

## 6. Open M4 risks

1. **Code-node sandbox correctness.** Highest-impact risk. Mitigation: get external review of the seccomp filter before 4.5 ships; gate the node behind a feature flag default-off if review is unavailable.
2. **pgvector performance at scale.** HNSW recall is great; insert latency degrades at 10M+ chunks. v1 ships for the small-to-medium case; v2 considers IVF or external Pinecone/Qdrant.
3. **Pydantic-ai breaking changes.** It's a pre-1.0 library. Pin exactly; bump deliberately.
4. **Sub-workflow + human-in-loop interactions.** A workflow that uses both creates a state-machine product. Tests cover the matrix; production usage may surface ordering bugs.
5. **Workflow execution under load.** One Dramatiq actor per Run scales linearly with workers. A workspace with 1000 concurrent runs needs ~1000 workers (cheap on Hetzner, but configure autoscaling).

---

## 7. Per-PR Definition of Done (M4 flavor)

```markdown
## Definition of Done — M4 agent-runtime

### Surface added
- Submodule(s) / nodes / model(s): <names>
- New deps: <package@version or none>
- Migration: <name or none>
- Scopes added: <names>

### Verification
- [ ] `uv run task lint && lint_types && test_fast` green
- [ ] `uv run task openapi_export` produces a clean diff
- [ ] `cd clients/packages/client && pnpm generate && cd ../../apps/web && pnpm typecheck` green
- [ ] `uv run alembic upgrade head && downgrade -1 && upgrade head` round-trips (if migration)
- [ ] **No-attribution `scan` job green** — non-negotiable for M4
- [ ] Manual: end-to-end exercise of the new surface

### Clean-room compliance
- [ ] No upstream source consulted while writing (rule from feedback_clean_room_policy)
- [ ] Module structure follows our conventions, not an external project's
- [ ] No variable names, file names, or comments referencing the upstream
- [ ] Reviewer confirms: "Reads like Rapidly, not like a port"

### Security
- [ ] No new untrusted-input surface escapes auth (workflows run as the workspace's identity, not as system)
- [ ] If the PR touches the credential store (4.7) or code sandbox (4.5): security checklist above
- [ ] LLM nodes (4.4): credential never logged; usage events scrubbed of prompt content if marked sensitive
```

---

## 8. Rollback

Each M4 PR is its own commit on main.

- 4.1: revert + `downgrade()` drops the 4 new tables.
- 4.2: revert; no schema impact.
- 4.3: revert; no schema impact.
- 4.4: revert; no schema impact. The `pydantic-ai-slim` extras stay in the lockfile.
- 4.5: revert; no schema impact. Sandbox subprocess code stays in git history for the next attempt.
- 4.6: revert + `downgrade()` drops vector tables. `DROP EXTENSION vector` only if no other domain came to depend on it.
- 4.7: revert + `downgrade()` drops `integration_credentials`. **Careful** — if any other PR after 4.7 stored credentials, those rows are lost.
- 4.8: revert + `downgrade()` drops dataset/eval tables.

---

## 9. After M4

`MEMORY.md` updates:

- Add `[M4 agent runtime backend complete (YYYY-MM-DD)](project_m4_agent_runtime_complete.md)`. Body: lists submodules, node catalog, security considerations (subprocess+seccomp sandbox, credential encryption), known limits (pgvector scale ceiling, sub-workflow recursion guard at 10).
- Annotate the pivot memory's Agents-chamber line: `[BACKEND LANDED 2026-MM-DD; UI is M5]`.

Next milestone: **M5 — Agent runtime UI (3 weeks).** `@xyflow/react`
graph editor, node palette, properties panel, run / eval / deploy
tabs. Lives in `clients/apps/web/src/app/(authenticated)/dashboard/[workspace]/agents/`.
Plan in `M5_EXECUTION.md` on user go-ahead.

# MCP Specification Reference — 2026-07-28

Offline reference for the current Model Context Protocol spec, distilled for a
server author. Written so this repo never has to re-fetch the spec to answer
"what does the protocol actually allow/require here?" Do not hand-edit into
staleness — when the upstream spec moves again, re-run the fetch pass and
regenerate this file rather than patching bullets ad hoc.

## Provenance

| Item | Value |
|---|---|
| Spec version (this document) | **2026-07-28** |
| Status | **Current** (final/stable release). A release-candidate blog post under the same version string was published 2026-05-29; the version was finalized/stabilized 2026-07-28. There is no newer draft version as of the check date. |
| Previous version | `2025-11-25` (now status **Final** — closed, will not change) |
| Checked | 2026-08-22 |

Sources fetched (all 2026-08-22 unless noted):
- `https://modelcontextprotocol.io/specification/` (index, version pointer)
- `https://modelcontextprotocol.io/specification/2026-07-28/versioning` (Draft/Current/Final model)
- `https://modelcontextprotocol.io/specification/2026-07-28/changelog` (authoritative diff vs `2025-11-25`)
- `https://modelcontextprotocol.io/specification/2026-07-28/{basic/index,basic/versioning,basic/patterns/mrtr,basic/patterns/subscriptions,basic/transports/stdio,basic/transports/streamable-http,server/index,server/tools,server/resources,server/prompts,server/discover,server/utilities/pagination,server/utilities/caching,server/utilities/completion,client/roots,client/sampling,client/elicitation,deprecated}`
- `https://raw.githubusercontent.com/modelcontextprotocol/specification/main/schema/2026-07-28/schema.ts` (ToolAnnotations, Implementation, ClientCapabilities, ServerCapabilities — verified against prose docs, which truncate on fetch)
- `https://modelcontextprotocol.io/extensions/{overview,tasks/overview}`
- `https://modelcontextprotocol.io/docs/2026-07-28/develop/clients/client-best-practices` (host-side guidance, non-normative)
- `https://modelcontextprotocol.io/seps/index` (SEP status table)
- `https://github.com/modelcontextprotocol/modelcontextprotocol` — releases, issues #1821, #1881, #1300, #1978, #204, #2808 (via `gh issue view`/`gh issue list`, live API, not cached search)
- `https://blog.modelcontextprotocol.io/posts/2026-07-28/` and `.../2026-07-28-release-candidate/`

All URLs above resolved successfully; nothing in this document rests on an unreachable source.

---

## 1. Architecture (unchanged shape)

Three roles: **Host** (LLM application), **Client** (connector inside the host, 1:1 with a server), **Server** (provides context/capabilities). Wire format is **JSON-RPC 2.0** throughout. Three server-offered primitives — **Tools** (model-controlled), **Resources** (application-controlled), **Prompts** (user-controlled) — plus one client-offered primitive, **Elicitation** (server-controlled, client-mediated). Full spec source of truth is the TypeScript schema (`schema/2026-07-28/schema.ts`); JSON Schema is generated from it.

---

## 2. The Big Change: MCP Is Now Fully Stateless

This is the headline change of `2026-07-28` and reshapes almost everything below. Quoting the spec directly:

> "MCP is a **stateless protocol**: all the information needed to process a request is contained in the request itself. A server processes each request independently; no state should be inferred from previous requests, even those on the same connection or stream."

Concretely:
- The `initialize` / `notifications/initialized` handshake is **gone**. There is no connection-scoped negotiation step.
- Protocol-level sessions and the `Mcp-Session-Id` header are **removed** from Streamable HTTP.
- Every request carries its own version and capabilities in `_meta` (below). Servers **MUST NOT** rely on prior requests on the same connection for context.
- An open stdio process or HTTP connection is **not** a session or conversation — servers **SHOULD** handle requests belonging to unrelated tasks/threads interleaved on the same channel, and clients **SHOULD NOT** use one connection as the lifetime boundary for a task.
- Cross-call state (shopping carts, transactions, job handles) **MUST** be carried as an explicit, server-minted identifier passed as an ordinary tool argument on subsequent calls — not inferred from the connection. See §7.6 "Stateful Tools" below.

This replaces `initialize` (SEP-2575, "Make MCP Stateless") and the earlier session-handle model (SEP-2567, "Sessionless MCP via Explicit State Handles"). Both are **Final**.

---

## 3. The `_meta` Contract (replaces `initialize`)

Every request/response now carries protocol metadata under `_meta`, keyed by reverse-DNS-style names. Reserved prefix rule: any `_meta` prefix whose second label is `modelcontextprotocol` or `mcp` is reserved for MCP use (`io.modelcontextprotocol/...`, `dev.mcp/...`).

**Per-request fields** (client → server), required unless noted:

| Key | Type | Required | Notes |
|---|---|---|---|
| `io.modelcontextprotocol/protocolVersion` | `string` | **Yes** | e.g. `"2026-07-28"` |
| `io.modelcontextprotocol/clientCapabilities` | `ClientCapabilities` | **Yes** | |
| `io.modelcontextprotocol/clientInfo` | `Implementation` | No | Clients **SHOULD** include it on every request |
| `io.modelcontextprotocol/logLevel` | `LoggingLevel` | No | Deprecated alongside Logging |

A request missing a required field is malformed: the server **MUST** reject it with JSON-RPC `-32602`, and on HTTP the status **MUST** be `400`. If a request needs a client capability the client didn't declare, the server **MUST** return `MissingRequiredClientCapabilityError` (`-32021`, `400` on HTTP) with `data.requiredCapabilities`.

**Per-response field** (server → client): `io.modelcontextprotocol/serverInfo` (`Implementation`) — servers **SHOULD** include it. `clientInfo`/`serverInfo` are self-reported and unverified — "Implementations **SHOULD NOT** use them to change behavior... and **SHOULD NOT** rely on them for security decisions."

Other reserved `_meta` keys: `progressToken` (progress notifications), `io.modelcontextprotocol/subscriptionId` (correlates a notification to its `subscriptions/listen` stream), `traceparent`/`tracestate`/`baggage` (W3C OpenTelemetry trace context — the one exception to the prefix rule).

Third-party `_meta` keys/extension identifiers use a vendor-owned reverse-DNS prefix (e.g. `com.example/my-extension`), same rule as Java packages.

---

## 4. Versioning & Backward Compatibility

Version strings are `YYYY-MM-DD` (date of last breaking change). Three states: **Draft** (in progress), **Current** (the live version, may still get backward-compatible additions), **Final** (closed, superseded). `2026-07-28` is Current.

**Negotiation**: no handshake — each request declares its version in `_meta`; the server accepts or rejects it independently per request. If unsupported, the server returns `UnsupportedProtocolVersionError` (`-32022`) listing what it does support. Client and server **MAY** support multiple versions simultaneously.

**`server/discover`** (new, replaces the identity/capability half of `initialize`) — servers **MUST** implement it; calling it is **optional** for clients:

```json
// Request
{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{...}}}
// Response
{"jsonrpc":"2.0","id":1,"result":{
  "resultType":"complete",
  "supportedVersions":["2026-07-28"],
  "capabilities":{"tools":{},"resources":{}},
  "_meta":{"io.modelcontextprotocol/serverInfo":{"name":"ExampleServer","version":"1.0.0"}},
  "instructions":"This server provides weather and resource utilities.",
  "ttlMs":3600000,"cacheScope":"public"
}}
```
Useful for (a) getting identity/capabilities/instructions in one call instead of probing `tools/list`+`resources/list`+`prompts/list`, and (b) as a **stdio backward-compat probe**: a client supporting both eras sends `server/discover` first — a `DiscoverResult` back means modern; a recognized modern JSON-RPC error means modern-but-wrong-version (retry with an advertised version); anything else (including timeout) means legacy — fall back to `initialize`.

On Streamable HTTP, era detection instead uses the POST response: a `400` whose body is a recognized modern JSON-RPC error (`UnsupportedProtocolVersionError`, `MissingRequiredClientCapabilityError`, `HeaderMismatch`) means modern; anything else means legacy — fall back to a GET probe for the old HTTP+SSE `endpoint` event.

**Interoperating with legacy (`initialize`-based) servers/clients** — versions `2025-11-25` and earlier — is explicitly supported via the above probes; implementations that need it retain `initialize` handling as a fallback path, not the default path.

---

## 5. Base Protocol: Messages, `resultType`, Errors

Requests/responses/notifications are standard JSON-RPC 2.0 with one addition: **every result now carries a required `resultType`**:

- `"complete"` — normal, final result.
- `"input_required"` — a `InputRequiredResult` (see MRTR, §6.2); the request isn't done yet.
- Extensions **MAY** add more `resultType` values, advertised via capabilities. An unrecognized `resultType` **MUST** be treated as invalid by the client.
- Compatibility: a result from an older server that omits `resultType` entirely **MUST** be treated as `"complete"`.

**Error code allocation** (new policy this revision): JSON-RPC reserves `-32000..-32099` for implementation-defined server errors; MCP partitions it:

| Range | Meaning |
|---|---|
| `-32700`, `-32600..-32603` | Standard JSON-RPC (parse/invalid request/method not found/invalid params/internal) |
| `-32000..-32019` | Legacy, implementation-defined. **MUST NOT** allocate new codes here. Exception: `-32002` (old resource-not-found) — receivers **MUST NOT** assume meaning for anything else in this band. |
| `-32020..-32099` | Reserved for the MCP spec itself; codes here are defined exclusively by the spec |

MCP-defined codes in the reserved band:

| Code | Name | Meaning |
|---|---|---|
| `-32020` | `HeaderMismatch` | Streamable HTTP header/body mismatch |
| `-32021` | `MissingRequiredClientCapability` | Request needs a capability the client didn't declare |
| `-32022` | `UnsupportedProtocolVersion` | Server doesn't support the requested version |

Retired codes implementations of this version **MUST NOT** emit: `-32002` (resource not found — now `-32602`; clients **SHOULD** still accept `-32002` from older servers), `-32042` (URL-elicitation-required, was `2025-11-25`-only).

New application-defined codes for anything the spec doesn't define **SHOULD** be allocated *outside* `-32768..-32000` entirely.

---

## 6. Message Patterns

Three patterns, and all implementations **MUST** support all three (they're part of the base protocol, unlike Tools/Resources/Prompts which are optional-per-capability):

### 6.1 Request/Response
Standard. Notifications get no response and **MUST NOT** include an ID.

### 6.2 Multi Round-Trip Requests (MRTR) — new, replaces server-initiated requests entirely

> "Servers **MUST** send server-to-client requests (such as `roots/list`, `sampling/createMessage`, or `elicitation/create`) using the MRTR pattern. The previous pattern of server-initiated requests is no longer supported. This is a breaking change."

**This directly answers "is sampling/elicitation/roots server-initiated?": no, not on the wire anymore.** The server cannot spontaneously push a JSON-RPC request to the client mid-connection. Instead:

1. Client sends a normal request (only `prompts/get`, `resources/read`, `tools/call` support this — servers **MUST NOT** send `InputRequiredResult` on any other method).
2. If the server needs more info, it responds (not requests) with `resultType: "input_required"`, an `inputRequests` map (keys → `elicitation/create` | `sampling/createMessage` | `roots/list` request objects), and an opaque `requestState` string.
3. Client fulfills the requests, then **retries the same method** with a new JSON-RPC `id`, adding `inputResponses` (keyed to match `inputRequests`) and echoing `requestState` verbatim.
4. Server reconstitutes context from `requestState` (and/or its own store) and returns the final `resultType: "complete"` result — or another `input_required` if still short.

```json
{"result":{"resultType":"input_required",
  "inputRequests":{"github_login":{"method":"elicitation/create","params":{"mode":"form","message":"...","requestedSchema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}}},
  "requestState":"AEAD-protected blob"}}
```

Rules worth knowing:
- Servers **MUST** include at least one of `inputRequests`/`requestState` in every `InputRequiredResult`.
- Servers **MUST NOT** put a request type in `inputRequests` the client hasn't declared capability support for.
- If `requestState` affects authorization/business logic, servers **MUST** integrity-protect it (HMAC/AEAD) and **SHOULD** bind principal + short TTL + originating-request digest inside it to bound replay. Clients **MUST NOT** inspect, parse, or modify `requestState` — echo it exactly.
- Servers **MUST NOT** assume a client will retry at all.

This is SEP-2322, **Final**.

### 6.3 Subscribe and Notify — `subscriptions/listen`

Replaces the old `resources/subscribe`/`unsubscribe` RPCs and the standalone HTTP GET stream with one long-lived request:

```json
{"method":"subscriptions/listen","params":{"notifications":{
  "toolsListChanged":true,
  "resourceSubscriptions":["file:///project/config.json"]
}}}
```
Filter fields (all optional): `toolsListChanged`, `promptsListChanged`, `resourcesListChanged`, `resourceSubscriptions` (array of URIs). Server **MUST** first send `notifications/subscriptions/acknowledged` (carrying the honored subset) before any other notification on the stream, and **MUST NOT** send unrequested notification types. Every notification on the stream carries `io.modelcontextprotocol/subscriptionId` = the JSON-RPC `id` of the `subscriptions/listen` request, for demux (critical on stdio, where all messages share one channel). A client **MAY** hold multiple concurrent subscriptions. On stdio, reconnection means the client **MUST** re-issue `subscriptions/listen` — no state survives.

Request-scoped notifications (`notifications/progress`, `notifications/message`) do **not** flow on this stream — they flow on the response stream of the request they belong to.

---

## 7. Tools

### 7.1 Capability & list semantics
Servers supporting tools **MUST** declare `{"capabilities":{"tools":{"listChanged": true|false}}}`. Servers declaring `tools` **MUST** respond to `tools/list`, and the result:
- **MAY** be empty, **MAY** change over time.
- **MUST NOT** vary per-connection or as a side effect of other requests (statelessness).
- **MAY** vary by the authorization on the request itself (credentials are per-request input, not connection state — so scoped-token filtering is explicitly sanctioned).
- **SHOULD** be returned in **deterministic order** — stated purpose: "enables clients to reliably cache the tool list and improves LLM prompt cache hit rates."

### 7.2 `tools/list` — request/response
Supports pagination (`cursor` in, `nextCursor` out) and now caching hints on every `resultType:"complete"` response:
```json
{"result":{"resultType":"complete","tools":[{...}],"nextCursor":"...","ttlMs":300000,"cacheScope":"public"}}
```
See §10.2 for the caching contract in full — it's new this revision and matters a lot at scale.

### 7.3 Tool definition — required vs optional fields

| Field | Required? | Notes |
|---|---|---|
| `name` | **Required** | Unique per server. SHOULD be 1–128 chars, case-sensitive, `[A-Za-z0-9_.-]` only. Server `name` from `serverInfo` is **not** guaranteed globally unique — don't use it to disambiguate across aggregated servers; prefix instead. |
| `description` | **Required** (human-readable functionality) | |
| `inputSchema` | **Required** | JSON Schema; **MUST NOT** be `null`. No-arg tools: `{"type":"object","additionalProperties":false}` is the *recommended* empty-object form. |
| `title` | Optional | Display name |
| `outputSchema` | **Optional** | See §7.4 |
| `annotations` | Optional | See §7.5. **MUST** be treated as untrusted unless from a trusted server. |
| `icons` | Optional | Array of `{src, mimeType?, sizes?, theme?}`. `src` **MUST** be `https:` or `data:` — clients **MUST** reject `javascript:`/`file:`/`ftp:`/`ws:`; **MUST** verify same-origin as the server; fetch without credentials; sniff magic bytes, don't trust the declared MIME type. |

Schema dialect: defaults to **JSON Schema 2020-12** if no `$schema` present; implementations **MUST** support 2020-12 and **MAY** support others (draft-07 shown as an example). `$ref` to a network URI **MUST NOT** be auto-dereferenced by default (SSRF guard); an opt-in mode **MUST** be disabled by default and **SHOULD** allowlist hosts / reject loopback+link-local+private ranges. Composition keywords (`anyOf`/`oneOf`/`allOf`/`if-then-else`, `$defs`) **SHOULD** be bounded (depth/subschema-count/time budget) to block validator-DoS schemas.

### 7.4 `outputSchema` — the validation-obligation question, answered directly
> "If an output schema is provided: Servers **MUST** provide structured results that conform to this schema. Clients **SHOULD** validate structured results against this schema."

So: `outputSchema` is fully **OPTIONAL** on the tool definition. When present, the server carries a **MUST**-conform obligation and the client carries a **SHOULD**-validate obligation (not MUST — a client that skips validation isn't non-conformant, but is exposed to bad data). Both parties **MUST** follow the `$ref` resolution rules above when validating against `inputSchema`/`outputSchema`. `structuredContent` (the field carrying the actual output) is unconstrained JSON when no `outputSchema` exists — object, array, string, number, boolean, or null are all valid — and it's unrelated to model-side "structured outputs"; it's server-produced result data.

### 7.5 Tool Annotations — exact fields and defaults (from `schema.ts`, unchanged this revision)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `title` | `string?` | — | Display title |
| `readOnlyHint` | `boolean?` | `false` | Tool does not modify its environment |
| `destructiveHint` | `boolean?` | `true` | May perform destructive updates. Only meaningful when `readOnlyHint == false`. |
| `idempotentHint` | `boolean?` | `false` | Repeat calls with same args have no additional effect. Only meaningful when `readOnlyHint == false`. |
| `openWorldHint` | `boolean?` | `true` | Interacts with an open world of external entities (e.g. web search) vs. closed (e.g. memory store) |

All annotations are **hints**, not guarantees, and **MUST** be considered untrusted unless the server is trusted.

### 7.6 `tools/call` — result shape, content, errors

```json
{"result":{"resultType":"complete","content":[{"type":"text","text":"..."}],"isError":false}}
```
Content block types: `text`, `image` (`data`+`mimeType`, base64), `audio` (same shape), `resource_link` (URI reference — "not guaranteed to appear in `resources/list`"), embedded `resource` (full inline resource). All content blocks support the shared `annotations` object (`audience: ["user"|"assistant"]`, `priority: 0.0–1.0`, `lastModified`).

**Structured content**: `structuredContent` (JSON value) is separate from `content`. For back-compat, a tool returning structured content **SHOULD** also serialize it into a `TextContent` block.

**Two distinct error mechanisms — don't conflate them:**
| Mechanism | Wire shape | When | Model can self-correct? |
|---|---|---|---|
| **Protocol error** | JSON-RPC `error` object (e.g. `-32602` unknown tool, malformed request) | Structural problem with the *request* | Less likely — clients **MAY** surface these to the model |
| **Tool execution error** | Normal result, `isError: true` in the result body | API failure, validation failure, business-logic failure | Yes — clients **SHOULD** surface these to the model so it can retry with adjusted args |

**Stateful tools** (non-normative guidance, since the protocol itself is now stateless): a server needing cross-call state (basket, transaction, browser context) returns an explicit opaque handle from a creation call and accepts it as an ordinary argument thereafter. Design notes from the spec: validate authorization against the handle on every call (a handle is a name, not a capability); make unauthenticated-server handles high-entropy bearer tokens with bounded lifetime; state the retention policy in the tool description so the model can see it; return a clear tool-execution error on an expired/unknown handle.

**`x-mcp-header`** (new): a JSON Schema extension property on an `inputSchema` property that tells Streamable HTTP clients to mirror that argument's value into an `Mcp-Param-{Name}` HTTP header, so intermediaries can route/meter on it without parsing the body. Only primitive (string/integer/boolean, not `number`) properties statically reachable via a pure `properties`-chain qualify; clients **MUST** reject (exclude from `tools/list`) any tool whose `x-mcp-header` violates the constraints, and **SHOULD** log why. Servers **SHOULD NOT** put secrets in it — header values are visible to intermediaries.

**Security** (server **MUST**): validate all inputs, implement access control, rate-limit, sanitize outputs. (Client **SHOULD**): confirm sensitive ops with the user, show inputs before calling, validate results before feeding the LLM, timeout calls, audit-log usage.

---

## 8. Resources

Capability: `{"resources":{"listChanged":true,"subscribe":true}}` — both sub-flags optional/independent; `subscribe` now specifically means "supports resource-specific updates via `subscriptions/listen`'s `resourceSubscriptions` filter" (not a separate RPC — see §6.3).

`resources/list` (paginated + cached, same envelope shape as tools), `resources/read` (also cacheable; **MAY** return multiple `contents` for one URI, e.g. a directory; **MAY** also respond `input_required` under MRTR), `resources/templates/list` (RFC 6570 URI templates, paginated + cached, args completable via `completion/complete`).

Resource fields: `uri` (required), `name` (required), `title`/`description`/`icons`/`mimeType`/`size` (optional). Content is text (`text` field) or binary (`blob`, base64). Same `annotations` shape as tool content (`audience`, `priority`, `lastModified`).

Standard URI schemes: `https://` (only when the *client* can fetch it directly, not proxied through the server), `file://` (may use XDG MIME types like `inode/directory` for non-regular files), `git://`. Custom schemes **MUST** be RFC 3986-conformant.

Errors: not-found is now `-32602` (was `-32002`; clients **SHOULD** still accept `-32002` from older servers for back-compat). Servers **MUST NOT** return an empty `contents` array to mean "not found" — that's ambiguous with "exists but empty." Servers **MUST** sanitize paths against traversal for `file://`.

---

## 9. Prompts

Capability: `{"prompts":{"listChanged":true}}`. `prompts/list` (paginated + cached). `prompts/get` (arguments filled in; **MAY** respond `input_required` under MRTR; args completable via `completion/complete`).

Prompt fields: `name` (required), `title`/`description`/`icons`/`arguments` (optional; each argument has `name`, `description`, `required`). `PromptMessage.role` is `"user"`|`"assistant"`; `content` supports the same block types as tool results (text/image/audio/resource_link/embedded resource).

---

## 10. Utilities

### 10.1 Pagination
Opaque-cursor model, **not** numbered pages. `cursor` in request, `nextCursor` in response when more remain. Page size is server-chosen — clients **MUST NOT** assume a fixed size. Clients **MUST** treat cursors as fully opaque (don't parse, don't infer end-of-list from cursor *value* — only from a *missing* `nextCursor`; an empty-string cursor is still valid and is **NOT** end-of-list). Invalid cursor → `-32602`. Covers `tools/list`, `resources/list`, `resources/templates/list`, `prompts/list`.

### 10.2 Caching (`ttlMs` / `cacheScope`) — new this revision, directly answers "any cache-hint mechanism added recently?"

> "Servers **MUST** include caching hints on results with `resultType: 'complete'`" for: `server/discover`, `tools/list`, `prompts/list`, `resources/list`, `resources/templates/list`, `resources/read`.

Two fields, added to every cacheable result:

| Field | Meaning |
|---|---|
| `ttlMs` | Integer ms the client **MAY** consider the result fresh, HTTP `max-age`-style. `0` = immediately stale. Absent → clients **SHOULD** assume `0` (should only happen talking to older servers). Negative → treat as `0`. Servers **MUST** send a value `>= 0`. It's a freshness *hint*, not a correctness guarantee — underlying data **MAY** change before TTL expiry. |
| `cacheScope` | `"public"` (no user-specific data — any client/gateway/proxy **MAY** cache and reuse across callers, even from an authenticated endpoint) or `"private"` (reusable only within the same authorization context — caches **MUST NOT** be shared across different tokens). |

Mechanics worth internalizing:
- Freshness check is `now < t_received + ttlMs`; clients **SHOULD NOT** treat TTL as a background-poll interval — check-on-access, not proactive refetch (and if you do poll anyway, **MUST** jitter+backoff).
- A `list_changed` notification **invalidates** a still-fresh cache immediately — TTL and push notifications are complementary, not exclusive; a server can offer one, the other, or both.
- Pagination interacts per-page: each page has its own TTL clock and **MAY** have a different `ttlMs` than sibling pages; there's **no** cross-page consistency guarantee if data changes mid-pagination; a full-consistency read means re-paginating from the start. `cacheScope` **MUST** be identical across all pages of one list request.
- Cache key = method + the parameters that affect the result (`uri` for reads, `cursor` for lists). MRTR-retry results (carrying `inputResponses`/`requestState`) **MUST NOT** be cached — their inputs aren't part of the key.
- Security: server implementors **MUST** apply real per-primitive access control and **MUST NOT** rely on `cacheScope` alone to gate access — `"public"` literally means "safe to hand to a different bearer token."

This is SEP-2549, **Final**.

### 10.3 Completion
`completion/complete` — argument autocomplete for prompt args and resource-template args. `ref` is `{"type":"ref/prompt","name":...}` or `{"type":"ref/resource","uri":...}`; `argument: {name, value}`; optional `context.arguments` carries already-resolved sibling args for multi-arg templates. Response: `completion.values` (max 100), optional `total`, `hasMore`.

---

## 11. Server `instructions` Field

Returned by `server/discover` (`instructions: "This server provides weather and resource utilities."`) — free-text, optional, described as "natural-language guidance for LLMs on how to use this server effectively." Not schema-constrained. Not to be confused with per-tool `description`. (Historically this lived in the `initialize` response pre-2026-07-28; it now lives in `server/discover`'s result alongside `capabilities` and `serverInfo`.)

---

## 12. Client Features

| Feature | Status | Server-initiated? |
|---|---|---|
| **Elicitation** | **Active** (not deprecated) | No longer wire-level server-initiated — delivered as an `inputRequests["...":{"method":"elicitation/create",...}]` entry inside an `InputRequiredResult`, i.e. the server *signals* the need via its response to a client request; see MRTR (§6.2) |
| **Sampling** | **Deprecated** as of `2026-07-28` (SEP-2577); ≥12 months before removal-eligible | Same MRTR-embedded mechanism (`sampling/createMessage`) |
| **Roots** | **Deprecated** as of `2026-07-28` (SEP-2577); ≥12 months before removal-eligible | Same MRTR-embedded mechanism (`roots/list`) |

**Elicitation** — two modes, both requiring `_meta.clientCapabilities.elicitation.{form,url}`: `form` (structured data, flat-object-of-primitives schema only — no nesting beyond enum arrays, formats limited to `email`/`uri`/`date`/`date-time`) and `url` (out-of-band navigation for sensitive data/OAuth/payment — data **MUST NOT** transit the MCP client). Servers **MUST NOT** use form mode for passwords/API keys/tokens/payment credentials — URL mode is mandatory for those. Responses use a 3-action model: `accept` (with `content` for form mode), `decline`, `cancel`. Extensive phishing-mitigation requirements apply to URL mode (server must bind the elicitation to the initiating user's session before completing any third-party OAuth exchange).

**Sampling** — lets a server request an LLM completion through the client, optionally with `tools`+`toolChoice` for agentic sub-loops (requires `sampling.tools` capability), model selection via `modelPreferences` (`costPriority`/`speedPriority`/`intelligencePriority` + advisory `hints`). `includeContext: "thisServer"|"allServers"` values are separately deprecated (since `2025-11-25`) — omit the field or use `"none"`.

**Roots** — informational filesystem hints (`file://` URIs only), *not* an access-control mechanism; the protocol does not enforce servers stay within them.

Migration guidance the spec gives for all three: Roots → pass paths via tool params/resource URIs/config; Sampling → integrate the LLM provider API directly; nothing prevents keeping them for existing integrations during the window — just "new implementations **SHOULD NOT** adopt."

---

## 13. Extensions Framework + the Tasks Extension

### 13.1 Extensions, generally
Extensions are optional, opt-in, negotiated capabilities beyond core — identified as `{vendor-prefix}/{extension-name}` (official = `io.modelcontextprotocol/...`, third parties use an owned reverse-DNS prefix). Declared by clients in `_meta.clientCapabilities.extensions` per-request and by servers in the `server/discover` `capabilities.extensions` map. **"Extensions are always disabled by default and require explicit opt-in from the developer."** Lifecycle: incubate as `experimental-ext-*` under a Working/Interest Group → SEP (Extensions Track) with a reference SDK implementation → Core Maintainer review → published to an official `ext-*` repo. This is SEP-2133, **Final**.

Currently official: **MCP Tasks**, **MCP Apps** (interactive UI), **OAuth Client Credentials**, **Enterprise-Managed Authorization** — all live in separate `ext-*` repos, not the core spec repo.

### 13.2 Tasks — status, precisely
**Not core protocol.** It is a **Final** SEP (SEP-2663, Extensions Track, 2026-04-27) defining the `io.modelcontextprotocol/tasks` **official extension**, spec'd in a separate `ext-tasks` repo. It graduated out of an earlier *experimental* in-core mechanism (SEP-1686) — this revision explicitly moved it **out of core and into an extension**, replacing blocking `tasks/result` with polling.

Mechanics: client declares `extensions: {"io.modelcontextprotocol/tasks": {}}` in its per-request `clientCapabilities`; server advertises the same in `server/discover`. A supported request (server's choice, unsolicited per-request — no client flag needed beyond the capability) returns `resultType: "task"` (`CreateTaskResult`: `taskId`, initial status, `ttlMs`, `pollIntervalMs`) instead of blocking. Client polls `tasks/get(taskId)`. Task states: `working` → `input_required` (client resolves via `tasks/update` with `inputResponses`) → terminal `completed` (`result` populated) | `failed` (`error` populated) | `cancelled`. `tasks/cancel` is cooperative, not guaranteed. Optional push via `notifications/tasks` over `subscriptions/listen`, but polling is the baseline — "If a server supports notifications, clients can rely on them instead of polling." Good fit: long external jobs, human-approval gates, unreliable connections, bulk operations. **Client support varies — check the extension client-support matrix before depending on it.**

---

## 14. Deprecated Features Registry (as of `2026-07-28`)

| Feature | Deprecated in | Earliest removal | Migration |
|---|---|---|---|
| Roots | `2026-07-28` | First revision on/after 2027-07-28 | Tool params / resource URIs / config |
| Sampling | `2026-07-28` | First revision on/after 2027-07-28 | Direct LLM provider API |
| Logging (`logging/setLevel`, `notifications/message`) | `2026-07-28` | First revision on/after 2027-07-28 | `stderr` (stdio) or OpenTelemetry |
| Dynamic Client Registration (RFC 7591) | `2026-07-28` | First revision on/after 2027-07-28 | Client ID Metadata Documents |
| `includeContext: "thisServer"/"allServers"` | `2025-11-25` | Follows Sampling's removal | Omit field, or `"none"` |
| HTTP+SSE transport (`2024-11-05`) | `2025-03-26` | 3 months after SEP-2596 reaches Final | Streamable HTTP |

A Deprecated feature stays in the spec and fully functional through the window; it's a "stop adopting it in new code" signal, not a "stop working" one. Governed by SEP-2596 (**Final**), which sets a minimum 12-month deprecation window (90-day expedited exception exists). Nothing has actually been Removed yet under this policy.

Also removed outright this revision (not merely deprecated — gone): `ping`, `logging/setLevel` as a standalone method, `notifications/roots/list_changed`, SSE stream resumability / `Last-Event-ID`, the GET-stream endpoint, `Mcp-Session-Id`, `notifications/elicitation/complete`, URL-mode elicitation's old `elicitationId` field.

---

## 15. Transports

### 15.1 stdio
Newline-delimited JSON-RPC over stdin/stdout; a message **MUST NOT** contain embedded newlines. Server **MAY** write UTF-8 to `stderr` freely (logs) — client **SHOULD NOT** treat `stderr` output itself as an error signal. No per-request streams — all responses/notifications share the one `stdout` channel, demuxed via JSON-RPC `id` (responses) or `io.modelcontextprotocol/subscriptionId` (subscription notifications). No requests flow server→client at all anymore (MRTR replaced that). Cancellation is `notifications/cancelled` referencing the request id. Shutdown: client closes stdin, waits, then escalates SIGTERM→SIGKILL (or `TerminateProcess`/Job Objects on Windows) if needed; server **SHOULD** exit promptly on EOF. Custom transports over other reliable byte streams (Unix sockets, TCP) **SHOULD** reuse this same framing.

### 15.2 Streamable HTTP
One POST endpoint. Every JSON-RPC message is its own POST; server replies either `application/json` (single object) or `text/event-stream` (SSE, scoped to *that* request only — progress/message notifications for that call, then the final response, then the stream closes). No client→server notifications are defined over HTTP in this core revision (only `notifications/cancelled`, and that's stdio-only — on HTTP, closing the SSE stream *is* the cancellation signal). Long-lived server→client notification delivery is exclusively via the `subscriptions/listen` response stream (§6.3) — there is no more standalone GET stream.

**Removed vs. `2025-03-26`–`2025-11-25` Streamable HTTP**: no more `Mcp-Session-Id` (mint/echo), no GET endpoint, no `Last-Event-ID` resumability, no server-initiated JSON-RPC requests on the SSE stream. A modern-only server facing this older traffic: GET/DELETE → `405`; stray `Mcp-Session-Id` → ignored; stray `Last-Event-ID` → ignored.

**Required headers on every POST** (mirroring select body fields so intermediaries can route without parsing JSON):

| Header | Source | Required for |
|---|---|---|
| `MCP-Protocol-Version` | `_meta.protocolVersion` | All requests. Mismatch vs body → `400` + `HeaderMismatch`. |
| `Mcp-Method` | `method` | All requests |
| `Mcp-Name` | `params.name`/`params.uri` | `tools/call`, `resources/read`, `prompts/get` |

Non-ASCII/whitespace/newline values use a `=?base64?{...}?=` sentinel encoding (also required for any value that would otherwise collide with that literal pattern). `x-mcp-header`-annotated tool parameters get mirrored as `Mcp-Param-{Name}` the same way (see §7.6). Header *names* are case-insensitive; header *values* are case-sensitive. Any header/body mismatch → server **MUST** reject with `400` + `-32020 HeaderMismatch`.

**Security**: **MUST** validate `Origin` (DNS-rebinding defense, invalid → `403`); local servers **SHOULD** bind `127.0.0.1` not `0.0.0.0`; **SHOULD** implement real auth. SSE responses **SHOULD** send `X-Accel-Buffering: no` (defeat proxy buffering) and periodic `:` comment keep-alives on long-lived streams.

### 15.3 Statelessness / session handling, explicitly
There is no session concept left at the protocol level on either transport (§2). "Session handling" for a real deployment means: the *server* mints and validates its own opaque handles for anything stateful (§7.6), and the *transport* is just plumbing — safely load-balanceable round-robin, no shared/sticky routing required. This is the explicit design goal stated in the blog announcement and confirmed throughout the base-protocol statelessness section.

---

## 16. Authorization (brief — not this doc's focus)

HTTP transports **SHOULD** conform to the MCP OAuth-based authorization framework; stdio **SHOULD NOT** (use environment-sourced credentials instead). This revision hardens it: `iss` (RFC 9207) **MUST** be validated before code redemption; Dynamic Client Registration is deprecated in favor of Client ID Metadata Documents (CIMD); client credentials **MUST** be keyed to the issuing authorization server and re-registered if it changes; `application_type` is now required on DCR to avoid OIDC redirect-URI conflicts. Full detail lives under `/specification/2026-07-28/basic/authorization/` — not expanded here since it wasn't this doc's priority axis.

---

## 17. Tool Discovery at Scale: the SEP-1821 Verdict

**Direct answer: dead, not adopted, no successor accepted.** Checked live against GitHub (`gh issue view`, not a cached search) on 2026-08-22:

- **SEP-1821 "Dynamic Tool Discovery"** (issue #1821, opened 2025-11-17) proposed exactly the mechanism you'd expect: an optional `query` string on `ListToolsRequestParams` plus a `ServerCapabilities.tools.filtering` flag, server does the filtering however it wants (substring/semantic/fuzzy). **Status: `Draft`, label `proposal` ("SEP proposal without a sponsor")** — it never found a sponsor. An automation bot flagged it inactive after 93 days (2026-02-23); a maintainer nudged again 2026-04-08 asking if the author still wanted to pursue it under the (by-then-changed) PR-based SEP process; the **issue was closed 2026-06-24** by maintainer @localden, explicitly noting SEPs had moved to a PR-based workflow and inviting a fresh PR if still wanted. No PR followed as of the check date. **It does not appear anywhere in the current SEP index** (`/seps/index`), which only lists SEPs that reached Draft-with-sponsor or later.
- **SEP-1300 "Tool Filtering with Groups and Tags"** (#1300) — had a sponsor (label `draft`), but is explicitly labeled **`rejected`**.
- **SEP-1881 "Scope-Filtered Tool Discovery"** (#1881) — same fate as #1821: `proposal` (no sponsor), **closed**.
- Related closed/dormant issues pointing at the same gap: #204 ("Open to tools/search and resources/search," dormant), #1978 ("Lazy Tool Hydration for Large Tool Sets," closed), #2808 ("MCP spec should address tool schema token overhead," closed), #1576 ("Mitigating Token Bloat," dormant).

So: **no protocol-level tool search/filter/query mechanism exists in `2026-07-28`, and none is in flight with a sponsor.** What the working group actually shipped instead, twice, addresses the *adjacent* problem from different angles:
1. **`ttlMs`/`cacheScope`** (SEP-2549, Final, §10.2) — makes repeated full-list fetches cheap, doesn't reduce the size of any single fetch.
2. **Host-side progressive discovery** (client-best-practices doc, §18b) — pushes filtering entirely into the client/host implementation via ordinary tools (`search_tools`), not a wire-protocol addition.

If you're building rancher-mcp's tool surface against this spec: there is no `tools/list` query param to lean on, now or on a committed roadmap. Anything resembling server-side filtering has to be your own extension (`extensions` capability, vendor-prefixed identifier) or client-side/host-side convention — not core protocol, and not safe to assume any client implements.

---

## 18. What This Means for a Large-Surface Server — Only What the Spec Actually Sanctions

Strictly from the normative spec (not opinion, not the host-side guidance in §18b):

1. **Pagination is real and required-support.** `tools/list` **MUST** be paginated correctly (opaque cursor, server-chosen page size) — a server with 300+ tools can and should paginate rather than dump everything in one response.
2. **Caching hints are now mandatory on your side.** You **MUST** emit `ttlMs`+`cacheScope` on every `tools/list`/`resources/*`/`prompts/list`/`server/discover` `"complete"` result. A large, rarely-changing tool catalog should carry a long `ttlMs` and `cacheScope: "public"` — this is the spec's actual, sanctioned lever for cutting repeat-fetch cost, not a nice-to-have.
3. **Deterministic ordering is a SHOULD, not decorative.** It exists specifically to make client-side and LLM-provider-side prompt caching of the tool list effective — stable ordering is a prerequisite for that caching to hit.
4. **`listChanged` + `subscriptions/listen` lets you avoid polling.** Advertise `listChanged: true` and clients can invalidate their cache the instant your catalog changes instead of re-polling on a timer.
5. **Per-request authorization-based filtering is explicitly legal.** The set returned by `tools/list` "MAY vary by the authorization presented on the request" — scoping a caller to a subset of 300+ tools by their token is spec-sanctioned, not a statelessness violation, as long as it's driven by the request's own credentials and not by hidden connection state.
6. **`x-mcp-header` is about routing, not context size** — don't reach for it to solve tool-count bloat; it mirrors argument values into HTTP headers for intermediary routing/metering, unrelated to how many tools you expose.
7. **There is no protocol-level search/filter query.** See §17. Don't design around one appearing soon.
8. **`outputSchema` is worth setting even though optional** — it's what lets a client (per §18b's "Programmatic Tool Calling") generate a typed function signature per tool instead of an untyped one, which is the actual lever against *result*-size context bloat once you're past discovery.

---

## 18b. Host-Side Guidance (non-normative — from `docs/develop/clients/client-best-practices`, not the spec itself)

This is client/host implementation advice, not protocol text — no RFC2119 language, nothing here is required of a conformant server. Included because it's the direct, current answer to "how do large tool counts get handled in practice," quoted verbatim where load-bearing.

**The named threshold** (this is the number the task asked for, exact quote):
> "Implement a threshold as a percentage of the context window. For example, 1%-5%. Load tool definitions. Once the threshold is reached, switch to progressive discovery."

**The three-layer pattern**, quoted:
> "**Layer 1: Catalog.** The host exposes a small set of meta-tools for searching available capabilities. A `search_tools` tool accepts a natural-language query and returns matching tool names with brief descriptions."
> "**Layer 2: Inspect.** Once the model identifies a candidate, it fetches the full definition (input schema, output schema, documentation) for that tool only."
> "**Layer 3: Execute.** The model calls the tool with full knowledge of its interface, having loaded only the definitions it needed."

Search strategy choices offered: keyword (BM25/regex), embedding-based, subagent-based (small fast model picks tools), hybrid — or defer to a model provider's built-in tool search (named: OpenAI, Anthropic) rather than build your own. Also: dynamic **server** (not just tool) connect/disconnect on demand, keyed off what a task/skill declares it needs.

**Programmatic tool calling / "code mode"** — the other named pattern: the model writes code against an auto-generated typed API (derived from each tool's `inputSchema`/`outputSchema`) that runs in a network-isolated sandbox; only `console.log`-style output returns to the model, not every intermediate tool result. Explicitly named as the lever against *result*-size bloat (as opposed to progressive discovery, which is the lever against *definition*-size bloat). Security model: sandbox has no direct network access, all calls route through the host broker which holds credentials and enforces the same per-call authorization policy as direct calls — "Approving the script does not grant blanket approval for every tool call it makes at runtime."

**Caching interaction called out explicitly**: treat a cached list as stale the instant a `list_changed` notification arrives, "even before its TTL expires" — and mind LLM-provider prompt-prefix caching separately: appending new tool definitions after the cache breakpoint (or routing everything through one stable `call_tool(name, args)` meta-tool) avoids invalidating the *provider's* prompt cache, which is a distinct cache from anything MCP defines.

---

## 19. Corrections vs. Prior Report

No prior-report file exists in this repository to diff against line-by-line (checked: no `docs/reference/` content, no other file referencing `2026-07-28` or the spec URLs existed before this document). Addressing the specific uncertainty the task flagged:

- **"A prior report referenced `2026-07-28` — verify current / superseded / RC."** Resolved: `2026-07-28` is **current and final**, not an RC snapshot. A same-numbered release-candidate blog post did exist earlier (`.../posts/2026-07-28-release-candidate/`, ~2026-05-29) — MCP's convention is that the version *string* is fixed at RC time and the *status* label (Draft/RC → Current) is what changes at finalization, so a report calling it "the 2026-07-28 spec" without further qualification was correct, just imprecise about which of the two blog posts it saw.
- **Common stale assumption worth flagging pre-emptively**: anyone whose mental model of MCP still includes `initialize`/`initialized`, `Mcp-Session-Id`, server-initiated sampling/elicitation/roots requests, or `resources/subscribe` as a standalone RPC is describing `2025-11-25` or earlier, not current. All four are gone (§2, §6.2, §6.3, §15.2). This is the single biggest thing to unlearn when reading older MCP material, including this server's own earlier design notes if any assumed the old handshake model.
- **Tasks**: if any prior note treated Tasks as core-protocol or still-experimental, correct: it's now a **Final**, official, opt-in **extension** living outside the core repo (§13.2) — a real status change from where it stood in `2025-11-25` (experimental, in-core).

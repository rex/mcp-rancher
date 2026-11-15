# Claude Code as an MCP Client — What It Actually Implements

What a server author can rely on when the client is Claude Code, established by
observation rather than inference. Companion to `mcp-spec.md` (what the protocol
allows) and `python-mcp-sdk.md` (what our SDK offers): this file is the third
leg — what the client on the other end does with it.

Client behaviour moves fast (30 releases in the five weeks before this was
written). Treat every row as dated, and re-run §8 before betting work on one.

## Provenance

| Item | Value |
|---|---|
| Checked | 2026-11-12 |
| Client examined | Claude Code **2.1.321** (the build bundled with the desktop app, driven headless). Latest published: 2.1.322. |
| Server used for the wire capture | Python `mcp` **2.3.0** (`MCPServer`) over stdio, behind a logging proxy |
| Our server at the time | rancher-mcp 1.64.0 on `mcp` 1.29.1 (legacy protocol) |
| Our server now | rancher-mcp **1.69.0** on `mcp` 2.3.0. Re-checked 2026-11-15 against Claude Code **2.1.325**: it negotiated `2026-07-28` with no `initialize` fallback. The "rancher-mcp" columns, §6's port notes and §7 are as of that check; everything about the client is still the 2026-11-12 capture. |

Three independent sources, and each row below says which one backs it:

- **W — wire.** Seen in a captured JSON-RPC exchange between the real client and a real server. Two runs: one-shot `claude -p`, and a kept-open `--input-format stream-json` session.
- **C — code.** Read in the client binary's embedded JavaScript (feature flags, capability construction, result conversion).
- **D — docs.** Stated in `code.claude.com/docs/en/mcp.md`, `env-vars.md`, or the published changelog, and not contradicted by W or C.

Where sources disagreed, W wins. One did: the community [extension support
matrix](https://modelcontextprotocol.io/extensions/client-matrix) shows no
Tasks support for Claude Code, and the wire shows it working.

---

## 1. Bottom line

1. **Claude Code is a modern client.** Its v2 runtime (MCP TypeScript SDK 2.0) is the default, and since 2.1.292 it probes every stdio server for protocol `2026-07-28` and uses it when the server answers.
2. **We are served on the modern path** — since 1.69.0, the port to `mcp` 2.x ([#2](https://github.com/rex/mcp-rancher/issues/2)). rancher-mcp answers the probe in 0.6–0.8 s and the session runs on `2026-07-28`; a client that never probes still gets the `2025-11-25` handshake from the same process. Through 1.68.0 we answered the probe with `-32602` and were connected on the legacy handshake, which put everything era-gated (tasks, MRTR, cache hints, the notification stream) out of reach.
3. **MCP tasks are real, and narrower than the headline.** Proven end to end here. But only on a `2026-07-28` connection; only in the terminal CLI (≥ 2.1.304), Agent SDK / stream-json sessions and GitHub Actions — **not the desktop app, not VS Code**, not subagents, not one-shot `-p`; and the Python SDK ships no Tasks support, so the server side is ours to write.
4. **Three server-author hooks are independent of the protocol era.** We use two of them, since 1.67.0 and 1.68.0 — see §3.

---

## 2. Capability matrix

"Era" is the protocol revision the feature needs: **any** also works on a
legacy connection; **modern** needs `2026-07-28`, which is what Claude Code
gives us since 1.69.0.

### Base protocol

| Feature | Claude Code | Src | Era | rancher-mcp today |
|---|---|---|---|---|
| Protocol `2026-07-28` (stateless, per-request `_meta`) | Yes — v2 runtime, default | W | — | **Spoken** (1.69.0) |
| `server/discover` | Sent first on stdio as an era probe, then again after connecting | W | modern | Answered in 0.6–0.8 s |
| Legacy `initialize` (≤ `2025-11-25`) | Yes, as the fallback | W | any | Still served, to clients that do not probe |
| `subscriptions/listen` | Opens one stream for `toolsListChanged` / `promptsListChanged` / `resourcesListChanged`. Does **not** request `resourceSubscriptions`. | W | modern | Acknowledged; nothing to send (static catalog) |
| `list_changed` notifications | Re-fetches the list (interactive: all three; `-p`/SDK: tools only) | D | any | Not emitted |
| Multi round-trip (`input_required`) | Yes — retries with `inputResponses` + `requestState` echoed | W | modern | Not used yet ([#8](https://github.com/rex/mcp-rancher/issues/8)) |
| Pagination | Follows `nextCursor` on every list call | D | any | Unpaginated |
| Cache hints (`ttlMs` / `cacheScope`) | Tolerated when absent (2.1.302). Its discovery cache covers remote servers only. | D | modern | SDK default: `ttlMs: 0`, `private` ([#3](https://github.com/rex/mcp-rancher/issues/3)) |
| Progress | Sends `progressToken` on **every** `tools/call`; renders progress; a notification resets the idle timeout | W+D | any | Only the three health rollups, two steps each, no message ([#13](https://github.com/rex/mcp-rancher/issues/13)) |
| Cancellation | `notifications/cancelled`; `tasks/cancel` for tasks | D | any | SDK default |
| Logging | Not requested — no `logLevel` key, no `logging/setLevel` | W | — | — |

### Server features

| Feature | Claude Code | Src | Era | rancher-mcp today |
|---|---|---|---|---|
| Tools | Yes | W | any | 206 |
| Annotations | `readOnlyHint` → runs in parallel with other read-only calls, and is safe to repeat. `idempotentHint` → safe to repeat once after a dropped connection (HTTP only). `title` displayed. | D | any | Set fleet-wide ✓ |
| `structuredContent` | **The model is given `JSON.stringify(structuredContent)`. Text blocks are dropped;** non-text blocks are kept. | W+C | any | Emitted ✓ |
| `outputSchema` | Validated client-side. A tool that declares one and returns no structured content, or content that does not conform, **fails the call**. Not part of what the model sees. | C | any | Published ✓ (parity-gated) |
| Images | Inline, plus the original saved to disk | D | any | — |
| Audio / PDF / binary | Saved to disk with the right extension, not dumped as base64 | D | any | — |
| `resource_link` | Yes | D | any | — |
| Resources | `resources/list` at connect; `@server:uri` mentions; list/read tools. Templates fetched lazily on first `@`. | W+D | any | 1 template |
| Prompts | Become `/mcp__<server>__<prompt>` commands; arguments split on whitespace | D | any | 10 ✓ |
| `completion/complete` | No evidence of use | — | — | — |
| Server `instructions` | Injected at session start; cut at **4,096** chars (2,048 before 2.1.296) | D | any | 1,914 chars |

### Client features and extensions

| Feature | Spec status | Claude Code | Src |
|---|---|---|---|
| Elicitation — form and URL | Active | **Yes, both modes, both eras.** Terminal dialog; card in cloud/desktop sessions; auto-cancelled when non-interactive; `Elicitation` hooks can answer. | W |
| Roots | Deprecated | Declared (`listChanged: true`) | W |
| Sampling | Deprecated | **No.** Never declared. | W |
| Tasks (`io.modelcontextprotocol/tasks`) | Official extension | **Yes** — see §5 | W |
| MCP Apps (`io.modelcontextprotocol/ui`) | Official extension | Declared only when the host sets `CLAUDE_CODE_MCP_APPS_HOST`. UI resources are hidden from resource lists. | C+D |
| Skills over MCP (`io.modelcontextprotocol/skills`) | Official extension | Not declared | W |
| Channels (`claude/channel`) | Claude-specific | Research preview, opt-in with `--channels`, **legacy connections only** | D |

The capability object, verbatim from the wire (`2026-07-28`):

```json
{"roots": {"listChanged": true},
 "elicitation": {"form": {}, "url": {}},
 "extensions": {"io.modelcontextprotocol/tasks": {}}}
```

On the legacy fallback `initialize` it is the same minus `extensions`.

---

## 3. Server-author hooks that are specific to Claude Code

All three are `_meta` keys on a tool's `tools/list` entry, so they are
independent of protocol era. rancher-mcp sets the first on five triage entry
points (1.67.0) and the second on the five tools annotated destructive (1.68.0;
`RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE=false` turns it off). The third
is unused.

| Key | Effect |
|---|---|
| `anthropic/alwaysLoad: true` | The tool loads upfront instead of being deferred behind tool search. Startup does not wait for the server because of it. The user's own `alwaysLoad: false` on the server overrides it. |
| `anthropic/requiresUserInteraction: true` | Claude Code shows the tool's permission prompt on **every** call, in every permission mode including `bypassPermissions`, with no "don't ask again"; allow-rules are ignored. Denied outright under `dontAsk` and behind `--permission-prompt-tool`. Must be the JSON boolean `true`. |
| `anthropic/maxResultSizeChars: N` | Raises that tool's persist-to-disk threshold from 50,000 chars up to a ceiling of 500,000. |

Limits worth designing against:

- **Tool search is on by default.** Only tool *names* and the server instructions load at session start. Tool search reads the first 4,096 chars of a description when matching, so the words Claude would search for belong at the start.
- Description caps: 4,096 chars for a tool loaded upfront, 16,384 for one loaded through tool search.
- Results: a warning at 10,000 tokens; over 25,000 tokens (`MAX_MCP_OUTPUT_TOKENS`) or 50,000 chars the result is written to a file and replaced by its path.
- Errors (`isError: true`): the text becomes the tool's error message; beyond ~11,000 chars only the first and last 5,000 survive.
- Full tool name (`mcp__<server>__<tool>`) over 128 chars: the tool is dropped.
- Input schemas: top-level property names must be 1–64 chars of `[A-Za-z0-9_.-]`; the schema must be valid draft 2020-12; a root-level `anyOf`/`oneOf`/`allOf` is flattened before it reaches the API.
- Time: no response *and* no progress for 30 min (stdio) or 5 min (remote) aborts the call. In an interactive main conversation a call still running after 2 min moves to a background task.

---

## 4. What the connection looks like on the wire

Captured against a `2026-07-28`-capable stdio server:

```
C→S  server/discover        id="server-discover-probe-1"   ← era probe, sent the moment the process starts
S→C  DiscoverResult         supportedVersions=["2026-07-28"]
C→S  server/discover        id=0
C→S  subscriptions/listen   id="listen:0"   {toolsListChanged, promptsListChanged, resourcesListChanged}
S→C  notifications/subscriptions/acknowledged
C→S  prompts/list · resources/list · tools/list      (in parallel)
C→S  tools/call             _meta: protocolVersion, clientInfo, clientCapabilities,
                                   claudecode/toolUseId, progressToken
```

`clientInfo` is `{name: "claude-code", title: "Claude Code", version, description, websiteUrl}`.

**The probe has a deadline, and it is about three seconds.** In one run the
server took 4.3 s to answer; 2.93 s after the probe the client sent a legacy
`initialize` on the same pipe. (The late `DiscoverResult` still won and the
connection ended up modern — but that is the client being forgiving, not a
contract.) In the other run the same server answered in 2.9 s and scraped
under. Cold-start time to first response for a Python server on `mcp` 2.3.0
was 2.9–4.3 s *while Claude Code was itself starting*; the bare SDK import is
0.7–1.4 s. Docs add that Claude Code may then skip probing a stdio server for
up to 7 days (`MCP_PROTOCOL_NEGOTIATION=auto` forces a re-probe).

So the fast-startup path in `__main__.py` is still load-bearing after the
port. Only the request it must answer quickly changes: `server/discover`
instead of `initialize`. It needs name, version, capabilities and
instructions — none of which require a tool module.

**Measured after the port (1.69.0, 2026-11-15).** rancher-mcp answers
`server/discover` in 0.56–0.62 s driven by hand and in 0.78 s under a real
Claude Code 2.1.325 start (`uv run`), against the ~3 s window; a legacy
`initialize` takes 0.39–0.48 s. While the tool modules finish importing in the
background, `__main__.py` holds every request that reads the registry — the
three list calls, `tools/call`, `prompts/get`, `resources/read`, the template
list — rather than only `tools/list` as before, so no early request can be
answered from a half-built catalog.

---

## 5. MCP tasks: the exact contract

A call becomes a task only if **all** of these hold:

- the connection is on `2026-07-28` (`MCP_SDK_GENERATION=v1` or `MCP_PROTOCOL_NEGOTIATION=legacy` rules it out);
- the session is a terminal CLI session, an Agent SDK or `--input-format stream-json` session, or a GitHub Actions run — on Claude Code ≥ 2.1.304 (2.1.319 without feature-flag fetching). In code the default is gated on the entrypoint being `cli`;
- the call comes from the main conversation, not a subagent;
- for non-interactive sessions, `CLAUDE_AUTO_BACKGROUND_TASKS=1`.

Claude Code signals this **per request**: a `tools/call` that may become a task
carries `"io.modelcontextprotocol/tasks": {}` under `clientCapabilities.extensions`,
and one that may not omits it. Both were captured — a one-shot `-p` call
omitted it, a stream-json call carried it. Answering with a task when it is
absent fails the call (`Unsupported result type 'task' for tools/call`).

The exchange, as captured:

```
C→S  tools/call {name}                          ext=[tasks]
S→C  {resultType:"task", taskId, status:"working", statusMessage,
      createdAt, lastUpdatedAt, ttlMs:null, pollIntervalMs:500}
C→S  tasks/get {taskId}        ← immediately, then every pollIntervalMs
S→C  {resultType:"complete", taskId, status:"working", statusMessage, …}
 …
S→C  {resultType:"complete", taskId, status:"completed",
      result:{content:[…], isError:false}, …}
```

What the model saw: a tool result saying the call "started server-side task …
moved to the background … you'll receive a notification with the result",
then, with no further prompt, a new turn carrying the result.

Rules that are easy to get wrong:

- `taskId`: ≤ 128 printable ASCII, no spaces, and **answerable on a new connection** — after a resume Claude Code asks about it over a fresh one.
- `pollIntervalMs` is clamped to 250–30,000 (default 2,000) and re-read from every `tasks/get` response.
- `statusMessage` is what the user sees as progress; omitting it in a response clears it.
- `failed` needs a top-level `error: {code, message}`; `input_required` carries `inputRequests` answered once per key via `tasks/update`.
- `-32602` from `tasks/get` means "unknown task": Claude Code retries for five minutes, then reports the outcome as unknown.
- **Not used:** `tasks/result`, `tasks/list`, `notifications/tasks`. Everything must be in `tasks/get`.
- A stdio server's process dies when Claude Code exits. The task survives only if the work lives somewhere else.

That last point is why tasks suit this server: a rollout or a drain already
lives in Kubernetes. A `taskId` can be a signed, opaque handle to the object
and the condition awaited, and `tasks/get` a live re-read — no job store, and
answerable across restarts by construction.

The Python SDK ships no Tasks support as of 2.3.0 ("Known gaps", 2.2.0 release
notes), but its public `Extension` API is enough. This is the core of what ran
against the real client — a reference for the shape, not production code:

```python
from mcp.server.mcpserver import Extension, MethodBinding
from mcp_types import RequestParams

TASKS = "io.modelcontextprotocol/tasks"

class TaskIdParams(RequestParams):
    task_id: str                      # MCPModel aliases this to `taskId`

class Tasks(Extension):
    identifier = TASKS                # advertised under capabilities.extensions

    def methods(self):
        return [MethodBinding("tasks/get", TaskIdParams, self._get),
                MethodBinding("tasks/cancel", TaskIdParams, self._cancel)]

    async def intercept_tool_call(self, params, ctx, call_next):
        declared = (ctx.session.client_capabilities.extensions or {})
        if TASKS not in declared or not is_long_running(params.name):
            return await call_next(ctx)          # plain call
        return {"resultType": "task", "taskId": mint(params), "status": "working",
                "createdAt": now(), "lastUpdatedAt": now(),
                "ttlMs": None, "pollIntervalMs": 2000}
```

A plain `dict` with a non-core `resultType` passes through the SDK's result
sieve untouched on a modern connection; that is by design ("a claimed
extension `resultType` shape is the extension's to own").

---

## 6. Python SDK 2.3.0 — facts the port needed

Read from the released wheel. Where these conflict with `python-mcp-sdk.md`
§10, these win. The second list is what the port itself turned up.

- `MCPServer(name, title, description, instructions, website_url, icons, version, …, *, extensions=, cache_hints=, middleware=, subscriptions=)`. `version=` is real, so the handshake-version stamp becomes a constructor argument.
- `import mcp.server.fastmcp` raises `ModuleNotFoundError` carrying a migration hint, rather than failing bare.
- `middleware=` and `Extension.intercept_tool_call` are the public replacements for patching `ToolManager.call_tool`.
- Elicitation: `ctx.elicit()` **fails on a modern connection** ("no back-channel for server-initiated requests"). The era-agnostic form is a resolver — `Annotated[ElicitationResult[T], Resolve(fn)]` where `fn` returns `Elicit(message, Schema)` — which emits MRTR on `2026-07-28` and a server request before it. Verified against the real client.
- Default cache hints are `ttlMs: 0`, `cacheScope: "private"`.
- A server that receives `server/discover` first serves that pipe as modern and rejects a later `initialize` with `-32022`.
- Requires `httpx2>=2.10`.

Found while porting (rancher-mcp 1.69.0):

- **`MCPServer`'s request handlers call the server's own public methods** — `list_tools`, `call_tool`, `list_prompts`, `get_prompt`, `list_resources`, `list_resource_templates`, `read_resource` — in both eras. Replacing one on the instance therefore interposes on every request without naming anything private. That is all `rancher_mcp.sdk_registry.wrap_server_method` does, and `tests/unit/test_sdk_registry.py` proves it through a real client in each era.
- **The server no longer checks `structuredContent` against `outputSchema` before sending.** 1.x did; in 2.x only the client does (the Python client in `ClientSession`, and Claude Code per §2). A schema/dump mismatch now fails at the client with nothing on the server noticing first, which leaves `tests/unit/test_output_schema_dump_parity.py` as the only early warning.
- The text content block is still rendered with `indent=2` (hence `result_compaction.py` survives the port).
- `Tool.run` turns an anticipated failure into `ToolError("Error executing tool <name>: …")` and a crash into `UnexpectedToolError("Error executing tool <name>")` with the detail withheld. The SDK decides what to log by that type, so an error wrapper must re-raise the same type.
- On a modern connection, list results carry `_meta["io.modelcontextprotocol/serverInfo"]` (`name`, `version`) and the cache hints.
- MCP types are snake_case in Python (`input_schema`, `structured_content`, `is_error`, `read_only_hint`); `model_dump(by_alias=True)` gives the wire shape. A hand-built dict of a wire entry silently measures the wrong keys.
- In-process client for tests: `from mcp import Client`, then `async with Client(server, mode="legacy" | "2026-07-28" | "auto")`. It exercises the real request path, including client-side output validation.
- `mcp/server/fastmcp.py` still ships as a shim, so `importlib.util.find_spec("mcp.server.fastmcp")` succeeds — only *importing* it raises. "The module is findable" proves nothing.
- `httpx` stays a direct dependency here for the Rancher client and `respx`; the SDK's own transport uses `httpx2`. Both are installed side by side.

---

## 7. What this means for rancher-mcp

Ranked by value per unit of effort, not by novelty.

**Shipped — independent of the protocol era**

1. **Compact the text content block** ([#5](https://github.com/rex/mcp-rancher/issues/5), 1.66.0). The SDK renders it with `indent=2`: 3,989 chars against 2,723 compact on `rancher_capability_domain_list`, **+46%**. Claude Code never shows that block to the model, so the cost lands entirely on the clients that do read it — the small-context hosts the footprint work was for.
2. **`anthropic/alwaysLoad` on the triage entry points** ([#6](https://github.com/rex/mcp-rancher/issues/6), 1.67.0). The `core` profile idea, delivered without removing a tool.
3. **`anthropic/requiresUserInteraction` on destructive tools** ([#7](https://github.com/rex/mcp-rancher/issues/7), 1.68.0). Our confirmation phrase can be satisfied by the model alone; this cannot.

**Unblocked by the port ([#2](https://github.com/rex/mcp-rancher/issues/2), shipped in 1.69.0) — not built yet**

4. **Elicitation-based confirmation** ([#8](https://github.com/rex/mcp-rancher/issues/8)) — spec-native, so it protects in every client, and the prompt can name what will be destroyed.
5. **Tasks and follow-to-completion workflows** ([#9](https://github.com/rex/mcp-rancher/issues/9)) — a new capability, not an optimization: the server has almost no long-running tools today.
6. **Cache hints and server identity** ([#3](https://github.com/rex/mcp-rancher/issues/3)) — a spec MUST, small practical gain on stdio.

**Corrections to what we believed**

- *"Modern connections have no `initialize` deadline, so the two-phase startup can go."* Wrong. The deadline moved to `server/discover` (§4).
- *"Do not design around the Tasks extension."* Stale. It was true of the SDK and is no longer true of the client.
- *The `tools/list` wire payload is what a model pays.* Not for Claude Code: with tool search it pays for names and instructions, then for whichever definitions it loads, and never for `outputSchema`. `tests/unit/test_context_footprint.py` measures the worst case — a client with no deferral — which is the right thing to ratchet, but it is an upper bound, not Claude Code's bill.

---

## 8. Re-verifying

The method, so this file can be regenerated rather than patched:

1. Put a line-logging proxy between the client and the server: copy stdin→child and child→stdout, appending each JSON-RPC line with its direction and a timestamp.
2. Behind it run an `MCPServer` from the SDK version of interest with three tools: one returning different text in `content` and `structuredContent`; one long-running, answered as a task by an `Extension` when the request carries the tasks extension; one that elicits.
3. Drive it with the real client under a scrubbed environment and `--strict-mcp-config`, once as `claude -p "<prompt>"` and once with `--input-format stream-json` plus `CLAUDE_AUTO_BACKGROUND_TASKS=1`, stdin held open until the task's result turn arrives.
4. Read the capture: the first request and its `_meta`, the capability object on `tools/call`, the gap between the probe and any `initialize`, and which marker the model reports.

Pass `--debug-file`: it records the runtime arm (`mcp runtime arm: v2`) and each task hand-off.

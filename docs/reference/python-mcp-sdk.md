# Python MCP SDK (`mcp`) — Reference for Modernization Planning

## Provenance

| | |
|---|---|
| Installed here | `mcp` **1.26.0** (`.venv/bin/python -c "import importlib.metadata as m; print(m.version('mcp'))"` → `1.26.0`) |
| Installed via | `pyproject.toml`: `mcp[cli]>=1.0` (unpinned upper bound — `uv.lock` resolved `1.26.0`) |
| Latest on PyPI | `mcp` **2.0.0**, released 2026-07-28 (`https://pypi.org/pypi/mcp/json`, `info.version`) |
| Latest 1.x (maintenance line) | `mcp` **1.29.0**, released 2026-07-28 — same day as 2.0.0, the final 1.x feature release |
| Source repo | `https://github.com/modelcontextprotocol/python-sdk` |
| v2 docs | `https://py.sdk.modelcontextprotocol.io/` (see confidence caveat in §10 — two fetches of this site produced contradictory specifics) |
| Date checked | 2026-08-22 |
| Method | Every claim about **1.26.0 behavior** below is grounded by reading the actual installed source at `.venv/lib/python3.12/site-packages/mcp/**` in this repo — not docs, not training data. Version history came from `https://pypi.org/pypi/mcp/json` (structured, authoritative) and `gh api repos/modelcontextprotocol/python-sdk/releases` (raw release bodies, not summarized). Two `WebFetch` calls to the v2 docs site were used for color on the unreleased-to-us v2 API and are flagged explicitly where used — they are the only lower-confidence material in this document. |

---

## 1. TL;DR

- We are **7 months and 3 minor releases behind** latest 1.x (1.26.0 → 1.29.0), and behind the whole **2.0.0 major rewrite** on top of that.
- `FastMCP.__init__` has **no `version` parameter**, full stop. `serverInfo.version` silently falls back to the installed `mcp` package's own version unless you reach into the private low-level `Server` object and set `.version` yourself. This repo already does exactly that (`src/rancher_mcp/server.py:149`) — it's the only seam the SDK exposes.
- There is **still no first-class "list all registered tools" API on `FastMCP` beyond `_tool_manager`** for internal `Tool` objects — but `await mcp.list_tools()` (public, async, spec-shaped) does exist on `FastMCP` itself in 1.26.0. See §4.5 for the precise distinction; this repo's own comments already document the workaround accurately.
- The **Tasks extension (SEP-1686)** exists experimentally in 1.26.0 (`server.experimental.enable_tasks()`, `mcp._mcp_server.experimental`) — but it was **deprecated in 1.28.0** and is a **confirmed "known gap" — entirely absent — in 2.0.0**. Do not design anything around it; the spec proposal it implements was pulled from the MCP spec.
- Pagination types exist end-to-end in the protocol (`Cursor`, `PaginatedRequest`/`PaginatedResult`) but **FastMCP's own `list_tools`/`list_resources`/`list_prompts` never implement cursoring** — they always return everything in one response, cursor or not. Only the Tasks `tasks/list` default handler actually cursors.
- **No tool filtering/toolsets concept exists anywhere in the SDK** (grepped the whole package — zero hits for "toolset"). Capability-gated tool visibility (what this repo does) is 100% userland, via overriding the low-level `list_tools` handler — which is exactly the pattern already in `src/rancher_mcp/__main__.py`.
- **No cache-hint concept exists in 1.26.0** (zero hits for cache/TTL semantics anywhere in the installed package).
- v2.0.0 **renames `FastMCP` → `MCPServer`** and reworks elicitation/sampling around a resolver-injection pattern because the new 2026-07-28 protocol revision removes mid-call server→client callbacks. This is a from-scratch migration, not a version bump — see §10.

---

## 2. Version landscape

Fetched via `gh api repos/modelcontextprotocol/python-sdk/releases` (raw bodies) and cross-checked against `pypi.org/pypi/mcp/json`:

| Version | Released | What changed |
|---|---|---|
| **1.26.0** | 2026-01-24 | **installed here** |
| 1.27.0 | 2026-04-02 | StreamableHTTP idle timeout (#1994); RFC 8707 OAuth resource validation; a "missing `TasksCallCapability`" backport to v1.x; conformance-test backports |
| 1.27.1 | 2026-05-08 | patch |
| 1.27.2 | 2026-05-29 | patch |
| 1.28.0 | 2026-06-16 | **Deprecates** (`DeprecationWarning`, not yet removed) the WebSocket transport (`mcp.client.websocket`, `mcp.server.websocket`) **and the experimental Tasks API** (`Server.experimental`, `ServerSession.experimental`, `ClientSession.experimental`, `experimental_task_handlers=`) — because Tasks (SEP-1686) was **removed from the MCP specification**; Python 3.14 support added |
| 1.28.1 | 2026-06-26 | patch |
| 1.29.0 | 2026-07-28 | **Final 1.x feature release.** Streamable HTTP request-body size limits (#3101); fixed `Context.report_progress()` routing to the originating request stream; tool-name validation now rejects a trailing newline; v1.x docs moved to `/v1/` and the line is now explicitly marked maintenance-only |
| 2.0.0 (+ a1/a2/a3/b1/b2/rc1) | 2026-06-11 → 2026-07-28 | **Major rework.** See §10. |

**v1.x is now in maintenance mode: security fixes only, per the 2.0.0 release notes** ("*v1.x is in maintenance mode and will only receive security fixes from now on*"). There will be no 1.30.0 with new features. If we stay on 1.x, 1.29.0 is the ceiling.

Protocol revisions this SDK version negotiates (`mcp/shared/version.py`, `mcp/types.py`):

```python
LATEST_PROTOCOL_VERSION = "2025-11-25"
DEFAULT_NEGOTIATED_VERSION = "2025-03-26"   # assumed if client sends none
SUPPORTED_PROTOCOL_VERSIONS = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]
```

v2.0.0 adds support for the **2026-07-28** revision while continuing to serve all of the above from the same server object — this is the revision that removes synchronous server→client callbacks mid-request (see §10).

Note: `mcp.server.fastmcp` (this SDK's ergonomic layer) is unrelated to the third-party `fastmcp` PyPI package (jlowin/fastmcp) — different project, same name. This document is entirely about the one bundled inside the official `mcp` distribution.

---

## 3. `FastMCP` construction and identity

### 3.1 Full constructor (`mcp/server/fastmcp/server.py`)

```python
class FastMCP(Generic[LifespanResultT]):
    def __init__(
        self,
        name: str | None = None,
        instructions: str | None = None,
        website_url: str | None = None,
        icons: list[Icon] | None = None,
        auth_server_provider: OAuthAuthorizationServerProvider[Any, Any, Any] | None = None,
        token_verifier: TokenVerifier | None = None,
        event_store: EventStore | None = None,
        retry_interval: int | None = None,
        *,
        tools: list[Tool] | None = None,
        debug: bool = False,
        log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
        host: str = "127.0.0.1",
        port: int = 8000,
        mount_path: str = "/",
        sse_path: str = "/sse",
        message_path: str = "/messages/",
        streamable_http_path: str = "/mcp",
        json_response: bool = False,
        stateless_http: bool = False,
        warn_on_duplicate_resources: bool = True,
        warn_on_duplicate_tools: bool = True,
        warn_on_duplicate_prompts: bool = True,
        dependencies: Collection[str] = (),
        lifespan: Callable[["FastMCP[LifespanResultT]"], AbstractAsyncContextManager[LifespanResultT]] | None = None,
        auth: AuthSettings | None = None,
        transport_security: TransportSecuritySettings | None = None,
    ): ...
```

**There is no `version` parameter.** Not an oversight to work around at the call site — it's absent from the signature entirely, and FastMCP never forwards anything version-like to the low-level `Server` it builds internally:

```python
self._mcp_server = MCPServer(
    name=name or "FastMCP",
    instructions=instructions,
    website_url=website_url,
    icons=icons,
    lifespan=...,
)
```

Compare to the low-level `Server.__init__` (`mcp/server/lowlevel/server.py`), which **does** take one:

```python
class Server(Generic[LifespanResultT, RequestT]):
    def __init__(
        self,
        name: str,
        version: str | None = None,
        instructions: str | None = None,
        website_url: str | None = None,
        icons: list[types.Icon] | None = None,
        lifespan: ... = lifespan,
    ): ...
```

### 3.2 How `serverInfo.version` actually gets set

`Server.create_initialization_options()` is the only place `server_version` is computed:

```python
def create_initialization_options(self, ...) -> InitializationOptions:
    def pkg_version(package: str) -> str:
        try:
            from importlib.metadata import version
            return version(package)
        except Exception:
            pass
        return "unknown"

    return InitializationOptions(
        server_name=self.name,
        server_version=self.version if self.version else pkg_version("mcp"),
        ...
    )
```

Since FastMCP never sets `self.version` on the `Server` it constructs, **every FastMCP-based server that doesn't explicitly patch this reports the installed `mcp` SDK's own version as `serverInfo.version`** — not the application's version. `mcp.server.fastmcp.__version__` is likewise just `importlib.metadata.version("mcp")` (`mcp/server/fastmcp/__init__.py`). There is no per-application version signal anywhere in FastMCP by default.

**This repo already found and fixed this** (`src/rancher_mcp/server.py`):

```python
def stamp_server_version(mcp: FastMCP) -> None:
    """``FastMCP.__init__`` accepts no ``version``, so it builds the low-level
    ``Server`` with ``version=None`` — and the SDK's fallback for that is
    ``pkg_version("mcp")``. Assigning the underlying ``Server.version`` is
    the only seam the SDK exposes for this."""
    from rancher_mcp import __version__
    mcp._mcp_server.version = __version__  # type: ignore[attr-defined]
```

This is still true in 1.26.0 and remains true through 1.29.0 — nothing in the 1.x changelogs between 1.26.0 and 1.29.0 touches this. Whether v2.0.0 adds a constructor-level `version=` is **unconfirmed and contradicted between two docs-site fetches** — see §10's confidence note. Don't assume it's fixed in v2 without checking the real v2 source first.

### 3.3 `instructions` / `website_url` / `icons` / (missing) `title`

All three are plain properties that proxy to the low-level `Server`:

```python
@property
def instructions(self) -> str | None: return self._mcp_server.instructions
@property
def website_url(self) -> str | None: return self._mcp_server.website_url
@property
def icons(self) -> list[Icon] | None: return self._mcp_server.icons
```

They flow into the wire `InitializeResult` as follows — note `instructions` sits at the top level, while `website_url`/`icons` live inside `serverInfo` (`Implementation`) alongside `name`/`version`:

```python
InitializeResult(
    protocolVersion=...,
    capabilities=...,
    serverInfo=Implementation(name=..., version=..., websiteUrl=..., icons=...),
    instructions=...,   # top-level, not on Implementation
)
```

`Implementation` inherits from `BaseMetadata` (`name` + `title`), same as `Tool`/`Resource`/`ResourceTemplate`/`Prompt` — but **neither `FastMCP.__init__` nor `Server.__init__` exposes a way to set a server-level `title`**. It's a real field on the wire type; there's just no constructor path to it. Same class of gap as `version`.

`Icon` (`mcp/types.py`) is uniform across every entity that can carry one:

```python
class Icon(BaseModel):
    src: str                    # URL or data URI
    mimeType: str | None = None
    sizes: list[str] | None = None
```

---

## 4. Tools

### 4.1 Registration surface

```python
def tool(
    self,
    name: str | None = None,
    title: str | None = None,
    description: str | None = None,
    annotations: ToolAnnotations | None = None,
    icons: list[Icon] | None = None,
    meta: dict[str, Any] | None = None,
    structured_output: bool | None = None,
) -> Callable[[AnyFunction], AnyFunction]: ...
```

Identical parameter list on `add_tool()`. There is **no `outputSchema` parameter** — it's derived, never hand-supplied (see 4.2). `annotations` is `ToolAnnotations` (`mcp/types.py`):

```python
class ToolAnnotations(BaseModel):
    title: str | None = None
    readOnlyHint: bool | None = None      # default false
    destructiveHint: bool | None = None   # default true; meaningful only if readOnlyHint == false
    idempotentHint: bool | None = None    # default false
    openWorldHint: bool | None = None     # default true
```
All hints, explicitly non-binding per the SDK's own docstring ("not guaranteed to provide a faithful description... never make tool use decisions based on ToolAnnotations from untrusted servers").

The internal registration object (`mcp/server/fastmcp/tools/base.py::Tool`, not the wire `types.Tool`) additionally carries `fn`, `fn_metadata`, `is_async`, `context_kwarg` — none of that is exposed through the decorator; it's all inferred from the function signature.

### 4.2 How `outputSchema` is derived (`mcp/server/fastmcp/utilities/func_metadata.py`)

`structured_output` has three states:
- `None` (default) — auto-detect from the return type annotation.
- `True` — force structured; **raises `InvalidSignature` at registration time** if the return type has no annotation, or if a schema can't be built for it.
- `False` — force unstructured; no schema is ever built, `structured_output=False` short-circuits before any return-type inspection.

When auto-detecting, `_try_create_model_and_schema()` branches on the return type:

| Return type | Handling |
|---|---|
| `BaseModel` subclass | used directly as the output model |
| `TypedDict` | converted field-by-field to a Pydantic model |
| `str`/`int`/`float`/`bool`/`bytes`/`None` | wrapped: `{"result": <value>}` |
| `dict[str, T]` | `RootModel[dict[str, T]]` |
| other generics (`list[T]`, `Union`, ...) | wrapped: `{"result": <value>}` |
| dataclass / plain class with type hints | converted via `get_type_hints()` into a Pydantic model |
| class with no type hints | **not serializable** — no output schema, tool stays unstructured |

The schema itself comes from `model.model_json_schema(schema_generator=StrictJsonSchema)`, a subclass that **raises instead of warns** on non-serializable types, so schema-generation failures fail loud at registration time rather than silently degrading.

`Tool.output_schema` (`tools/base.py`) is a `cached_property` reading `self.fn_metadata.output_schema`. `FastMCP.list_tools()` sets `outputSchema=info.output_schema` unconditionally — `None` when the tool is unstructured, so the wire `Tool.outputSchema` is naturally absent for unstructured tools.

### 4.3 Validation — input and output are handled asymmetrically

There are **two independent validation layers** stacked on every call: FastMCP's own Pydantic-based validation, and the low-level `Server.call_tool()` handler's `jsonschema`-based validation. FastMCP explicitly **disables the second layer for input**, but not for output:

```python
# FastMCP._setup_handlers()
self._mcp_server.call_tool(validate_input=False)(self.call_tool)
# comment in source:
# "we disable the lowlevel server's input validation. FastMCP does ad hoc
#  conversion of incoming data before validating - for now we preserve
#  this for backwards compatibility."
```

So on the way in: only `FuncMetadata.call_fn_with_arg_validation()` validates — via `arg_model.model_validate()` — after a `pre_parse_json()` pass that re-parses stringified JSON arguments (a known Claude Desktop quirk: it sometimes sends `["a","b"]` as the *string* `'["a","b"]'` rather than an actual array).

On the way out, if `outputSchema` is defined, **both** layers run: `FuncMetadata.convert_result()` validates through the Pydantic `output_model`, and separately the low-level `call_tool()` handler re-validates the serialized `structuredContent` against `tool.outputSchema` via `jsonschema.validate()` before it ever reaches the wire. If `outputSchema` is defined but the tool didn't actually return structured content, the low-level handler produces an explicit `Output validation error: outputSchema defined but no structured output returned` — this is checked independently of FastMCP.

### 4.4 Error wrapping

`Tool.run()` (`tools/base.py`) wraps any exception from the underlying function:

```python
except UrlElicitationRequiredError:
    raise  # special-cased — becomes a proper -32042 protocol error, not a tool error
except Exception as e:
    raise ToolError(f"Error executing tool {self.name}: {e}") from e
```

`ToolManager.call_tool()` raises `ToolError(f"Unknown tool: {name}")` for a missing name. The low-level `call_tool()` handler catches *everything* that reaches it and converts it into an `isError=True` `CallToolResult` rather than a JSON-RPC protocol error — tool failures are reported as normal (if flagged) results, not transport-level errors, except for the URL-elicitation special case.

### 4.5 `ToolManager` internals, and whether a public enumeration API exists now

```python
# mcp/server/fastmcp/tools/tool_manager.py
class ToolManager:
    def get_tool(self, name: str) -> Tool | None: ...
    def list_tools(self) -> list[Tool]: ...          # public method — plain name, no underscore
    def add_tool(self, fn, *, name=None, ...) -> Tool: ...
    def remove_tool(self, name: str) -> None: ...     # raises ToolError if missing
    async def call_tool(self, name, arguments, context=None, convert_result=False) -> Any: ...
```

The nuance the previous investigation's note ("no public enumeration API") undersold: **`ToolManager.list_tools()` is, and has been, a completely normal public method** — nothing about the method itself is private. What's private is only the *attribute name* FastMCP stores the manager under: `self._tool_manager`. Reaching it (`mcp._tool_manager.list_tools()`) is exactly what this repo does in five places (`metrics.py`, `audit.py`, `tools/support/errors.py`, `tools/support/capability_unavailable.py`, `server.py`), with its own comment calling this "the established, deliberate escape hatch."

**What is new-ish and genuinely public as of 1.26.0**: `FastMCP` itself now has plain async methods, no underscore, that do real work:

```python
async def list_tools(self) -> list[MCPTool]: ...              # spec-shaped: MCPTool (inputSchema/outputSchema/...)
async def call_tool(self, name: str, arguments: dict) -> ...: ...
async def list_resources(self) -> list[MCPResource]: ...
async def list_resource_templates(self) -> list[MCPResourceTemplate]: ...
async def read_resource(self, uri) -> Iterable[ReadResourceContents]: ...
async def list_prompts(self) -> list[MCPPrompt]: ...
async def get_prompt(self, name, arguments=None) -> GetPromptResult: ...
```

So: `await mcp.list_tools()` **is** a fully public, non-underscored enumeration API today — but it returns wire-shaped `types.Tool` objects (JSON-schema dicts, no `fn`, no `is_async`, no `context_kwarg`), it's `async` (needs a running loop, awkward from synchronous registration-time code), and it re-derives the list from `_tool_manager` on every call rather than exposing the richer internal `Tool` objects this repo's error-suggestion/metrics/audit code actually needs. For internal-object access at registration time (this repo's real use case), `_tool_manager.list_tools()` remains the only path — there still isn't a `mcp.tools` property or similar. Both facts are true simultaneously; "there is no public API at all" is no longer accurate, "there is a public API that replaces `_tool_manager` for our use case" is also not accurate.

---

## 5. Resources

```python
def resource(
    self, uri: str, *,
    name: str | None = None, title: str | None = None, description: str | None = None,
    mime_type: str | None = None, icons: list[Icon] | None = None,
    annotations: Annotations | None = None, meta: dict[str, Any] | None = None,
) -> Callable[[AnyFunction], AnyFunction]: ...
```

`Annotations` here (`mcp/types.py`) is the generic content-annotation type (`audience: list[Role] | None`, `priority: float 0.0-1.0 | None`) — distinct from `ToolAnnotations`.

Whether a decorated function becomes a plain `Resource` or a `ResourceTemplate` is decided at decoration time, purely structurally: if the URI contains `{...}` **or** the function takes any parameters, it's a template; a template requires the URI's `{param}` set to exactly equal the function's parameter set (minus any `Context`-typed parameter). Mismatches raise `ValueError` immediately, at decoration time, not at call time.

**Template matching is a naive string substitution, not RFC 6570** (`mcp/server/fastmcp/resources/templates.py`):

```python
def matches(self, uri: str) -> dict[str, Any] | None:
    pattern = self.uri_template.replace("{", "(?P<").replace("}", ">[^/]+)")
    match = re.match(f"^{pattern}$", uri)
    return match.groupdict() if match else None
```

Every `{param}` becomes `(?P<param>[^/]+)` — single path segment, no slashes, no reserved-expansion, no query-string templates, no multi-value expansion. `ResourceManager.get_resource()` checks concrete resources first, then walks templates in registration order and uses the first structural match.

`list_resources()` / `read_resource()` / `list_resource_templates()` are plain, unpaginated (see §7) — same pattern as tools. Reading a resource returns `Iterable[ReadResourceContents]`; returning bare `str`/`bytes` from a resource handler is deprecated (`DeprecationWarning` at the low-level `Server.read_resource()` handler) in favor of yielding `ReadResourceContents` objects, present already in 1.26.0.

Resource *subscriptions* (`resources/subscribe`, `notifications/resources/updated`) exist only at the low-level `Server` — `subscribe_resource()` / `unsubscribe_resource()` decorators, both marked `# pragma: no cover` in the SDK's own test-coverage annotations (lightly used/tested). **FastMCP does not expose these at all** — no `@mcp.subscribe_resource()`. Worse: `Server.get_capabilities()` hardcodes the advertised capability regardless of whether you've registered a subscribe handler:

```python
resources_capability = types.ResourcesCapability(
    subscribe=False,   # literal, not conditioned on SubscribeRequest in self.request_handlers
    listChanged=notification_options.resources_changed,
)
```

If you build subscription support directly on the low-level `Server`, the capability negotiation will still tell clients `subscribe: false` unless you post-process `get_capabilities()`'s return value yourself.

---

## 6. Prompts and completion

```python
def prompt(
    self, name: str | None = None, title: str | None = None,
    description: str | None = None, icons: list[Icon] | None = None,
) -> Callable[[AnyFunction], AnyFunction]: ...
```

Arguments are never declared explicitly — `Prompt.from_function()` derives `PromptArgument` entries straight from the function's own JSON schema (via the same `func_metadata()` used for tools):

```python
for param_name, param in parameters["properties"].items():
    required = param_name in parameters.get("required", [])
    arguments.append(PromptArgument(name=param_name, description=param.get("description"), required=required))
```

The wire `PromptArgument` (`mcp/types.py`) has only `name` / `description` / `required` — no `title`, even though `Prompt` itself (via `BaseMetadata`) does.

A prompt function can return `str | Message | dict | Sequence[...]` (sync or async); results are normalized into `list[Message]` by `Prompt.render()`. `UserMessage`/`AssistantMessage` are thin `Message` subclasses that auto-wrap a bare `str` into `TextContent`.

**Completion (argument autocomplete)** is a first-class, if separate, feature — registered once per server via a single handler that dispatches on reference type, not per-prompt/per-resource:

```python
@mcp.completion()
async def handle_completion(
    ref: PromptReference | ResourceTemplateReference,
    argument: CompletionArgument,          # {name, value} — value is the partial input
    context: CompletionContext | None,     # {arguments: dict[str,str]} — previously-resolved vars
) -> Completion | None:
    return Completion(values=["opt1", "opt2"], total=None, hasMore=None)
```
`FastMCP.completion()` is a one-line passthrough to `self._mcp_server.completion()` — same object as the low-level API, no FastMCP-specific wrapping. `Completion.values` is capped at 100 items per the SDK's own docstring.

---

## 7. Low-level `Server` — what FastMCP hides, and how to reach it

Every `FastMCP` instance carries the real object at `self._mcp_server` (typed `mcp.server.lowlevel.server.Server`, aliased `MCPServer` in `fastmcp/server.py`). This is the escape hatch for everything FastMCP doesn't decorate for: resource subscriptions, custom `NotificationOptions`, raw request/notification handler registration, and the experimental Tasks API.

```python
mcp = FastMCP("my-server")
mcp._mcp_server.version = "9.9.9"                    # §3.2
mcp._mcp_server.list_tools()(custom_handler)          # overwrites FastMCP's default — this repo does this for lazy/gated tool lists
mcp._mcp_server.experimental.enable_tasks()            # §9's Tasks caveat applies
```

`create_initialization_options(notification_options=None, experimental_capabilities=None)` builds the `InitializationOptions` sent at handshake. FastMCP always calls it with **no arguments** (`run_stdio_async`, `sse_app()`, `streamable_http_app()` all call `self._mcp_server.create_initialization_options()` bare) — so `NotificationOptions()` defaults apply: `prompts_changed=False, resources_changed=False, tools_changed=False`. Every `listChanged` capability FastMCP advertises is `False` unless you drop to the low-level `Server` and pass your own `NotificationOptions` through a custom `run()` call.

`get_capabilities()` derives each capability from whether a corresponding handler is registered in `self.request_handlers` — `ListToolsRequest` present → `tools` capability advertised, etc. — **except** `resources.subscribe`, which is hardcoded `False` regardless (§5), and `tasks`, which is added by `ExperimentalHandlers.update_capabilities()` only if any task-related handler was registered.

`Server.run()` accepts `stateless: bool = False` directly (separate from FastMCP's `stateless_http` Settings field, though `streamable_http_manager.py` wires FastMCP's setting through to this parameter).

---

## 8. Transports

FastMCP supports three, chosen via `mcp.run(transport=...)`:

| Transport | Entry point | Notes |
|---|---|---|
| `"stdio"` (default) | `run_stdio_async()` | wraps `mcp.server.stdio.stdio_server()` |
| `"sse"` | `run_sse_async(mount_path=None)` | legacy — most of `sse_app()`'s branches are marked `# pragma: no cover` in the SDK itself, a soft signal it's not the emphasized path anymore |
| `"streamable-http"` | `run_streamable_http_async()` | current recommended HTTP transport |

Mount/path settings are all `FastMCP.__init__` keyword args (§3.1): `host`, `port`, `mount_path`, `sse_path` (`/sse`), `message_path` (`/messages/`), `streamable_http_path` (`/mcp`).

**`stateless_http: bool`** — when true, `StreamableHTTPSessionManager` creates a brand-new `StreamableHTTPServerTransport` per HTTP request with no session tracking, no `Mcp-Session-Id` continuity, and no event store; each request gets its own `Server.run(..., stateless=True)`. When false (default), sessions are tracked by a server-generated `Mcp-Session-Id` header (`uuid4().hex`), reused across requests, and cleaned up on transport crash.

**`json_response: bool`** — toggles whether Streamable HTTP responses are single JSON bodies or SSE streams.

**`event_store: EventStore | None`** + **`retry_interval: int | None`** — SSE resumability: if set, disconnected clients can reconnect with `Last-Event-ID` and replay missed events; `retry_interval` is surfaced to clients as the SSE `retry:` field.

**ASGI integration**: `FastMCP.streamable_http_app()` / `sse_app()` return plain `starlette.applications.Starlette` instances. `FastMCP.custom_route(path, methods, ...)` registers arbitrary Starlette routes alongside the MCP endpoint (health checks, OAuth callbacks) — explicitly documented as bypassing auth, since it's meant for public/pre-auth endpoints. `FastMCP.session_manager` (property) exposes the `StreamableHTTPSessionManager` directly for mounting **multiple** FastMCP servers inside one larger Starlette/FastAPI app — only valid after `streamable_http_app()` has been called once (lazy init), and explicitly documented as one-shot: a `StreamableHTTPSessionManager` cannot be `.run()` twice.

---

## 9. Protocol capability matrix

| Capability | 1.26.0 (installed) | 1.29.0 (latest 1.x) | 2.0.0 (latest overall) | Notes |
|---|:---:|:---:|:---:|---|
| **Pagination** (`Cursor`, `nextCursor`) — *protocol types* | Yes | Yes | Yes (types repackaged, see below) | `PaginatedRequest`/`PaginatedResult` cover tools/resources/prompts/templates/tasks list endpoints |
| **Pagination** — *FastMCP's tools/resources/prompts list handlers* | **No** | No (unchanged in changelogs) | Unconfirmed | FastMCP always returns the full list in one response; cursor is accepted on the wire but ignored |
| **Pagination** — *Tasks `tasks/list`* | Yes | Yes | N/A (Tasks absent) | The one list endpoint whose default handler genuinely cursors (`store.list_tasks(cursor)` → `nextCursor`) |
| **Tasks extension (SEP-1686)** | Experimental, lowlevel-only (`server.experimental.enable_tasks()`) | **Deprecated** (`DeprecationWarning`, since 1.28.0) | **Absent** — explicit "known gap" in the 2.0.0 release notes | The spec proposal was removed from MCP; a *different* future extension (SEP-2663) is promised, unshipped. Don't build on this. |
| **Tasks — per-tool declaration** (`Tool.execution.taskSupport`) | Type exists (`ToolExecution.taskSupport: forbidden\|optional\|required`); **no path to set it via `@mcp.tool()`** | same | N/A | Would require hand-building a `types.Tool` and a custom `list_tools` handler |
| **Elicitation — form mode** | Yes (`ctx.elicit()`, primitives + string-sequences only, schema-validated) | Yes | Reworked — see below | `elicit_with_validation()` rejects nested/complex schemas at call time |
| **Elicitation — URL mode** (out-of-band OAuth/payment/credential flows) | Yes (`ctx.elicit_url()`, error code `-32042`, `UrlElicitationRequiredError`) | Yes | Reworked — see below | Newer, more sophisticated than form mode; both present already in 1.26.0 |
| **Sampling** (`session.create_message()`) | Yes | Yes | Reworked — see below | |
| **Sampling with tool use** (`tools=`/`tool_choice=` params, `CreateMessageResultWithTools`) | Yes | Yes | Unconfirmed | Present in 1.26.0 already — not a recent addition relative to us |
| **`listChanged` notifications — wire methods** | Yes (`send_tool_list_changed()` etc. on `ServerSession`) | Yes | Reworked (`subscriptions/listen` replaces this per docs-site, unverified) | Methods exist but nothing calls them automatically (see below) |
| **`listChanged` — capability advertised by default** | **No** (`NotificationOptions()` defaults all three to `False`; FastMCP never overrides) | No | Unconfirmed | You must both call the notifier yourself *and* thread custom `NotificationOptions` through a low-level `run()` call |
| **Icons** (`Icon{src,mimeType,sizes}`) | Yes — Tool/Resource/ResourceTemplate/Prompt/server (`Implementation`) | Yes | Yes | Fully reachable via every FastMCP decorator already |
| **Cache hints** (TTL/staleness on list or read results) | **No** — zero hits anywhere in the installed package | No (not in any 1.27–1.29 changelog) | Reported by docs site only (`ttlMs`/`cacheScope`) — **not corroborated by the official release notes**, treat as unverified | |
| **Tool filtering / toolsets** (declared groups/subsets of tools) | **No** — zero hits for "toolset" anywhere in the SDK | No | Not mentioned in release notes | Capability-gated visibility is 100% userland — override the low-level `list_tools` handler, as this repo already does |
| **WebSocket transport** | Yes, undeprecated | Deprecated (1.28.0) | **Removed** | |
| **Resource subscriptions** | lowlevel only; capability hardcoded `subscribe=False` regardless (§5) | same | Unconfirmed | |
| **Structured tool output / `outputSchema`** | Yes, fully described in §4.2 | Yes | Yes (mechanism presumably intact — decorator API said unchanged) | |
| **`FastMCP(version=...)`** | **No** — confirmed absent from the signature (§3.1) | No | **Contradicted between two docs-site fetches** — one says no `version=` exists at all (negotiated per-request instead), the other lists `version` as the last positional constructor parameter. Not independently verifiable without the real v2 source. | See §10's confidence note |

---

## 10. Upgrade considerations

### 1.26.0 → 1.29.0 (staying on 1.x)

Low-risk, no breaking changes found in any of the three intervening changelogs (1.27.0/1.28.0/1.29.0 bodies, read directly via `gh api`, not summarized). What we'd gain:
- Streamable HTTP idle timeout (1.27.0) and request-body size limits (1.29.0) — both real hardening for an HTTP-exposed server.
- A `Context.report_progress()` routing bug fix (1.29.0) — progress notifications now correctly go to the originating request's stream.
- RFC 8707 OAuth resource validation (1.27.0) — relevant only if/when auth is added.
- Python 3.14 support (1.28.0) — not currently load-bearing (`requires-python = ">=3.12"`).
- Tool-name validation now rejects a trailing newline (1.29.0) — trivial but free.
- **We'd also inherit the Tasks/WebSocket deprecation warnings** (1.28.0) — if `pytest` is configured with `filterwarnings = ["error"]` anywhere and any test path touches WebSocket or `.experimental`, that test would start failing on upgrade. Grep found no WebSocket usage and no `.experimental` usage in this repo, so this is very unlikely to bite, but worth a `make test` check after bumping.

This is a safe, mechanical `mcp[cli]>=1.0` re-resolve; there's no reason to stay on 1.26.0 specifically.

### 1.29.0 → 2.0.0 (major rewrite — not a drop-in upgrade)

This is a full migration, not a version bump. From the **official release notes** (`gh api .../releases/tags/v2.0.0`, direct quote, high confidence):

- **`FastMCP` is renamed `MCPServer`.** The release notes state the decorator API itself (`@mcp.tool()`/`@mcp.resource()`/`@mcp.prompt()`) is unchanged, but the class name, and therefore every import in this codebase (`from mcp.server.fastmcp import FastMCP`, used in `server.py` and every `tools/*.py` file), changes.
- **The low-level `Server` is "rebuilt around a shared dispatcher engine"** — unspecified scope of internal change; `_mcp_server`-reaching code (§3.2, §7 — real patterns in this repo) should be treated as needing re-verification, not assumed compatible.
- **Multi-round-trip requests replace synchronous server→client callbacks.** At the new 2026-07-28 protocol revision, "the server can no longer call the client" mid-request — the release notes describe a `Resolve(fn)` dependency-injection parameter that lets a tool "return the question" and get resumed later, serving both protocol eras from one function body. This is architecturally significant for anything using `ctx.elicit()` / `ctx.elicit_url()` / `session.create_message()` today — this repo doesn't currently use any of them (grep found no `ctx.elicit`/`create_message` calls in `src/`), which limits our exposure, but any future use of elicitation or sampling should be designed with this in mind rather than against the current synchronous model.
- **`mcp.types` becomes an alias for a standalone `mcp-types` package** (`mcp_types`), versioned in lockstep with `mcp`. Anything doing `from mcp.types import X` presumably keeps working via the alias, per the release notes, but the import surface is no longer self-contained in the `mcp` distribution.
- **Tasks extension (SEP-1686/SEP-2663) is absent** — explicit known gap. Nothing to lose here since we never shipped on it.
- **WebSocket transport is removed entirely.** Not used by this repo.
- **Hardened stdio** (handler subprocesses and stray prints kept off the JSON-RPC stream; stdout diverted to stderr while serving) — a straightforward win for an stdio server, guards against exactly the "an accidental `print()` corrupts the protocol stream" bug class.
- **OAuth**: RFC 9207 issuer validation, SEP-990 identity-assertion flow, client-credentials extension — not currently relevant (no `auth=` configured in this repo today).
- v1.x stays on security-fix-only maintenance; there is a documented migration guide at `py.sdk.modelcontextprotocol.io/migration/` and a `What's new in v2` tour.

**Confidence note on specifics beyond the above**: two separate `WebFetch` calls against the v2 docs site (`/whats-new/`, `/migration/`) were used to look for exact signatures and code patterns, since v2.0.0 isn't installed here and can't be read directly. They **directly contradicted each other** on whether `MCPServer.__init__` takes a `version=` parameter (one said no such parameter exists at all; the other listed it as the final positional constructor argument) and gave two different import paths for the renamed class (`mcp.server.MCPServer` vs `mcp.server.mcpserver.MCPServer`). Both also asserted a wholesale camelCase→snake_case field rename across every protocol type (`tool.inputSchema` → `tool.input_schema`, `result.isError` → `result.is_error`) with `model_dump(by_alias=True)` required to get wire format — a claim not corroborated anywhere in the official release notes body. **Treat every specific from those two fetches (exact signatures, exact code samples, the field-casing claim, the `Resolve()`/`Elicit()` code shown in §whats-new) as unverified direction, not fact**, until read from the actual v2 source or a fresh, single, cross-checked fetch. The load-bearing facts in this section — rename, decorator API stability, resolver-based multi-round-trip, Tasks absence, WebSocket removal, stdio hardening, OAuth additions — come from the official GitHub release notes body, fetched raw via `gh api`, and are high-confidence.

**Recommendation for planning purposes**: budget the 2.0.0 move as a rewrite of the FastMCP integration layer (`server.py`, `__main__.py`, every `_mcp_server`/`_tool_manager` reach-in), not a dependency bump. The 1.26.0 → 1.29.0 bump, by contrast, is close to free and should happen independently of any 2.0.0 decision.

---

## 11. Type-checking under pyright strict

This repo runs `typeCheckingMode = "strict"` (`pyproject.toml`) against a dependency that ships `py.typed` but has real gaps in strict-mode coverage. The project already carries explicit, working accommodations — all grounded in this repo's actual code, not hypothetical:

1. **`reportMissingTypeStubs = false`** is set project-wide in `[tool.pyright]`, specifically to tolerate `mcp`'s partial stub coverage despite it declaring `py.typed`.
2. **Reaching `_mcp_server` or `_tool_manager` needs `# type: ignore[attr-defined]`** (pyright strict's `reportPrivateUsage` fires on leading-underscore attribute access across module boundaries):
   ```python
   mcp._mcp_server.version = __version__  # type: ignore[attr-defined]
   mcp._mcp_server.list_tools()(_lazy_list_tools)  # type: ignore[attr-defined]
   ```
3. **Scoped `Any` typing at the call site**, rather than loosening the enclosing function's own signature, when a function that legitimately takes `mcp: FastMCP` also needs to reach `_tool_manager`:
   ```python
   mcp_internals: Any = mcp
   populate_from_tools(mcp_internals._tool_manager.list_tools())
   ```
4. **`# pyright: ignore[reportUnusedFunction]`** on inner functions registered purely through decorator side effects (`@mcp.resource(...)`, same class of issue applies to `@mcp.tool()`/`@mcp.prompt()`) when defined inside a factory function — pyright strict can't see that the decorator's registration call is the "use," so it flags the nested `def` as dead code:
   ```python
   @mcp.resource("rancher://{resource_id}", ...)
   async def _rancher_resource(resource_id: str) -> str:  # pyright: ignore[reportUnusedFunction]
       ...
   ```

No other `mcp`-related type-suppression exists in `src/` beyond these four sites (8 total `type: ignore`/`pyright: ignore` in the whole tree; the other 4 are unrelated dict-narrowing cases in `redaction.py`/`envelope.py`). This is a short, stable list — worth re-auditing after any SDK bump, since a new minor could either fix these gaps (stub improvements) or introduce new ones.

---

## 12. Source map

Everything above was read directly from `.venv/lib/python3.12/site-packages/mcp/` in this repo. Quick index for future reference:

```
mcp/
├── types.py                                    protocol types — 1999 lines, every Request/Result/Notification/Capability
├── shared/
│   ├── version.py                              SUPPORTED_PROTOCOL_VERSIONS
│   ├── exceptions.py                            McpError, UrlElicitationRequiredError
│   └── experimental/tasks/                      Tasks extension internals (store, queue, capabilities, resolver)
└── server/
    ├── models.py                                InitializationOptions (4 fields, trivial)
    ├── session.py                                ServerSession — create_message, elicit_form/elicit_url, send_*_notification
    ├── elicitation.py                            elicit_with_validation(), elicit_url(), schema primitive-type enforcement
    ├── streamable_http_manager.py                stateless vs stateful session handling
    ├── lowlevel/
    │   ├── server.py                             Server — the real handshake/capability/dispatch logic (803 lines)
    │   └── experimental.py                       ExperimentalHandlers — enable_tasks(), task capability negotiation
    └── fastmcp/
        ├── server.py                             FastMCP, Context, Settings — the ergonomic layer (1350 lines)
        ├── tools/{base,tool_manager}.py           Tool, ToolManager
        ├── utilities/func_metadata.py             input/output schema derivation (533 lines) — the algorithm in §4.2
        ├── resources/{resource_manager,templates}.py   ResourceManager, ResourceTemplate — URI matching in §5
        └── prompts/{base,manager}.py               Prompt, PromptManager
```

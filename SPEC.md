# amaca — Spec (v0.2, decisions locked)

A web-based front end that lets a user run scientific computing codes
through a browser. The codes do the work; amaca handles the user
interface, job lifecycle, and result presentation.

The first concrete target is CCFLY, but **the system must accept any code
that fits a small adapter contract**. Generality is a goal, not a side
effect.

---

## 1. What amaca is (and isn't)

**It is:**
- A long-lived service exposing an HTTP API + a SPA web UI.
- A *thin* layer: form generation, job submission, status, results rendering.
- A plugin host: a new code is added by writing one adapter file + one schema.

**It isn't:**
- A scientific code itself. It runs other people's codes; it does not
  reimplement them.
- A general workflow engine (no DAGs, no inter-job piping in v1).
- A cluster scheduler. We assume the code runs locally to amaca or on
  resources the adapter knows how to reach.

---

## 2. Core abstraction — the **Code Adapter**

Every code plugged into amaca is described by one object:

```python
class Code(Protocol):
    name: str                    # "ccfly", "dqc", ...
    title: str                   # human label
    version: str

    InputSchema: type[BaseModel]   # pydantic — drives form auto-generation
    OutputSchema: type[BaseModel]  # drives result display

    def run(self, inputs: InputSchema, ctx: JobContext) -> OutputSchema: ...

    # Optional:
    def estimate_cost(self, inputs) -> CostHint: ...   # rough s/min/hr/MB
    def render(self, outputs, ui) -> None: ...         # custom UI renderer
```

The `InputSchema` / `OutputSchema` pydantic models are what makes this
work. They're consumed at three places:

- **UI**: form generated from `InputSchema` (text fields, sliders, file
  uploads, dropdowns — driven by field types + metadata).
- **API**: request/response validation, with a generated OpenAPI spec
  for free.
- **Storage**: every job persists its validated inputs and (when
  finished) its outputs as JSON.

Default renderers cover scalars, tables (pandas), plots
(matplotlib/plotly figure JSON), and downloadable files. Custom
renderers are an escape hatch, not the norm.

### Plugin packages

Real adapters live in **separate packages** that depend on `amaca` and
on the underlying code, and register themselves via Python's standard
entry-point mechanism. The bundled `Demo` adapter exists only as the
canonical test fixture; amaca core never imports any specific
scientific code.

```toml
# pyproject.toml of e.g. amaca-ccfly
[project]
name = "amaca-ccfly"
dependencies = [
    "amaca",
    "ccfly @ git+https://github.com/smvinko/ccfly-v2.git@v2.0.0",
]

[project.entry-points."amaca.codes"]
ccfly = "amaca_ccfly.adapter:CcflyCode"
```

amaca picks plugins up at process startup via
`amaca.core.load_entry_points()`. To pin the underlying code to a
specific release (and isolate the webserver from ongoing upstream
development), the adapter package pins the code by tag or commit
in its own `dependencies` — independent of any amaca version.

---

## 2a. Auth model

amaca uses **GitHub OAuth** for first-party identity, plus **personal API
tokens** for programmatic access (CLI, scripts, third-party tools).

```python
class User:
    id: int
    github_id: int            # immutable GitHub user id
    github_username: str      # current handle (can change on GitHub)
    email: str | None
    role: Literal["admin", "user"] = "user"
    disabled: bool = False
    created_at: datetime
    last_login_at: datetime | None

class ApiToken:
    id: int
    user_id: int              # owner
    name: str                 # user-supplied label ("laptop CLI")
    prefix: str               # first 8 chars, indexed (for lookup display)
    hash: str                 # bcrypt of the full token; full token shown once
    last_used_at: datetime | None
    created_at: datetime
    revoked_at: datetime | None
```

- **Access control:** all `/api/jobs*` endpoints require auth.
  Non-admins only see jobs where `owner_id == self.id`. Admins see all
  jobs and have `/api/users` available.
- **Registration:** `AMACA_ALLOWED_GITHUB_USERS` env var holds a
  comma-separated allowlist of GitHub usernames. First successful OAuth
  login from a listed user creates their `User` row. Anyone not on the
  list gets a clean "not authorised" page.
- **Bootstrap admin:** `AMACA_ADMIN_GITHUB_USERS` env var marks the
  initial admin(s); their `User.role` is promoted on first login.
- **Sessions:** signed cookies (HttpOnly, SameSite=Lax), 30-day expiry,
  rotated on each request. Backed by `itsdangerous` (or
  `starlette.middleware.sessions`).
- **Tokens:** generated as `amk_<32 url-safe bytes>`. Stored only as
  bcrypt hash; full token returned exactly once at creation. Token
  carries the user's role at creation time (refreshes on each request).

OAuth env vars: `AMACA_GITHUB_CLIENT_ID`, `AMACA_GITHUB_CLIENT_SECRET`,
`AMACA_SESSION_SECRET` (random 32+ bytes). Callback URL registered with
GitHub:
`http://localhost:8000/api/auth/callback` for dev,
`https://<host>/api/auth/callback` for deployed.

---

## 3. Architecture

```
 ┌──────────┐    HTTP/WebSocket    ┌──────────────┐   in-process / queue   ┌────────────┐
 │ Browser  │ ─────────────────── ▶│  amaca API   │ ────────────────────── ▶│  Worker(s) │
 │ (SPA)    │                      │  (FastAPI)   │                         │  + Adapter │
 └──────────┘                      └──────┬───────┘                         └─────┬──────┘
                                          │                                       │
                                          │           ┌───────────────┐           │
                                          └──────────▶│ Job/state DB  │◀──────────┘
                                                      │ (SQLite/Postgres)
                                                      └───────────────┘
```

Job lifecycle: `queued → running → (succeeded | failed | cancelled)`,
with timestamps and a streaming log channel.

---

## 4. API surface (v1)

```
# Auth
GET    /api/auth/login                  redirect to GitHub OAuth
GET    /api/auth/callback               OAuth callback → set session cookie
POST   /api/auth/logout                 clear session
GET    /api/auth/me                     who am I (current user + role)
POST   /api/auth/tokens                 create a personal API token
GET    /api/auth/tokens                 list my tokens
DELETE /api/auth/tokens/{id}            revoke a token

# Codes
GET    /api/codes                       list registered codes + metadata
GET    /api/codes/{name}                code detail (full schemas + version)

# Jobs (all require auth; non-admins see only their own)
POST   /api/jobs                        submit (body = {code, inputs})
GET    /api/jobs                        list (paginated, filterable)
GET    /api/jobs/{id}                   status + (when finished) outputs
DELETE /api/jobs/{id}                   cancel a running job
GET    /api/jobs/{id}/logs              tail of stdout/stderr
GET    /api/jobs/{id}/files/{name}      download a file artifact
WS     /api/jobs/{id}/stream            push updates (status, log lines)

# Admin (role = admin)
GET    /api/users                       list all users
PATCH  /api/users/{id}                  set role / disable
```

All payloads JSON; files via standard multipart/streaming. OpenAPI doc
auto-generated and served at `/api/docs`.

Auth accepted via either the session cookie (set by OAuth callback) or
an `Authorization: Bearer <token>` header (API tokens, for CLI/scripts).

---

## 5. Tech stack — proposed defaults

| Layer | Default | Why |
|---|---|---|
| Backend | **FastAPI** | async-native, generates OpenAPI from Pydantic, well-trodden |
| Validation | **Pydantic v2** | one schema language for forms + API + storage |
| Job queue | **arq** (Redis) | minimal, async-native, fits FastAPI; alt: in-proc thread pool for MVP |
| DB | **SQLite** via SQLAlchemy | trivial setup; switchable to Postgres later |
| Frontend | **SvelteKit + Vite** | "slick" with less ceremony than React; smaller bundles |
| Plot rendering | **Plotly** (browser-side) | interactive zoom/hover for free |
| Auth (v1) | **GitHub OAuth + API tokens** (multi-user, allowlist-gated) | low friction for a developer tool; same identity people already have; tokens cover CLI use |
| Tests | **pytest** + **playwright** (UI smoke) | one test stack for both layers |

This stack runs cleanly on the same Homebrew Python 3.14 venv style we
just set up. Backend in `amaca/`, frontend in `frontend/`.

---

## 6. Repository layout (proposed)

```
amaca/
├── SPEC.md                  # this file
├── README.md
├── pyproject.toml
├── amaca/                   # the Python package
│   ├── __init__.py
│   ├── api/                 # FastAPI routes
│   ├── core/                # Code / JobContext / Adapter protocols
│   ├── codes/               # bundled adapters (each: name.py + tests)
│   ├── db/                  # SQLAlchemy models + migrations
│   ├── workers/             # arq tasks
│   └── ui/                  # static SPA build output
├── frontend/                # SvelteKit source
│   ├── src/
│   ├── package.json
│   └── ...
└── tests/
    ├── test_adapter_contract.py    # any Code must satisfy this
    ├── test_api.py
    └── test_e2e_browser.py
```

Adapters live in `amaca/codes/` for the first wave; later they can be
distributed as plugins (entry-point group `amaca.codes`) so external
codes plug in without forking amaca.

---

## 7. The "Hello, Code" adapter — used to test the base

To make the base testable before any real code is wired in, v1 ships a
**Demo adapter** that takes a few inputs (an integer, a float, a string,
maybe a small file upload), sleeps for a configurable duration to
exercise the async path, and returns a small table + a sine-wave plot.

Every test in `test_adapter_contract.py` runs against this demo
adapter, so the base is fully exercised end-to-end without depending on
CCFLY's existence.

---

## 8. Decisions (locked for v0.2)

| # | Decision | Setting | Notes |
|---|---|---|---|
| 1 | Job duration spread | seconds to ~30 min | async architecture; WS for status, polling fallback |
| 2 | Where jobs run | same host as amaca for v1 | adapter signature unchanged when remote execution is added later |
| 3 | Single-user vs multi-user | **multi-user**, GitHub OAuth + API tokens | see §2a |
| 4 | File handling cap | 100 MB / file, 30-day auto-cleanup | adjustable via env later |
| 5 | Frontend framework | **SvelteKit** | confirmed |
| 6 | Backend language | Python | adapters may shell out to anything |
| 7 | Live result streaming | log stream yes; intermediate results no in v1 | revisit if a real code wants partial outputs |
| 8 | Persistence of past runs | yes, keep last 1000 per code | DB cleanup task at v2 if needed |

---

## 9. What I'd build first (once spec is approved)

1. `amaca/core/` — `Code` protocol, `JobContext`, `JobStatus`, `Adapter` base class.
2. `amaca/codes/demo.py` — the Hello-Code adapter (#7 above).
3. `amaca/db/models.py` — `Job`, `JobLog`, `Artifact`.
4. `amaca/api/` — the 7 endpoints in §4.
5. `amaca/workers/` — async runner that calls a Code's `run(...)`.
6. `tests/test_adapter_contract.py` + `tests/test_api.py` — must be green.
7. Minimal SvelteKit shell: code list → form → submit → live status → result page.
8. `tests/test_e2e_browser.py` — Playwright walks through 6 → 7 against the demo adapter.

At that point amaca runs end-to-end against the demo code; wiring CCFLY
becomes just "add `amaca/codes/ccfly.py` with the right Input/Output
schema and a `run(...)` that shells out to the CCFLY binary."

# amaca — Spec (draft v0.1)

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
GET    /api/codes                       list registered codes + metadata
GET    /api/codes/{name}                code detail (full schemas + version)

POST   /api/jobs                        submit (body = {code, inputs})
GET    /api/jobs                        list (paginated, filterable)
GET    /api/jobs/{id}                   status + (when finished) outputs
DELETE /api/jobs/{id}                   cancel a running job
GET    /api/jobs/{id}/logs              tail of stdout/stderr
GET    /api/jobs/{id}/files/{name}      download a file artifact
WS     /api/jobs/{id}/stream            push updates (status, log lines)
```

All payloads JSON; files via standard multipart/streaming. OpenAPI doc
auto-generated and served at `/api/docs`.

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
| Auth (v1) | **None** (single-user, localhost-only) | unblock work; add token auth in v2 |
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

## 8. Decisions you need to make (or defer with my default)

| # | Decision | My default | When it matters |
|---|---|---|---|
| 1 | **Job duration spread** for codes you plan to add | seconds to ~30 min; sync HTTP is dead, polling/websocket required | architecture (already assumed async); affects worker timeouts |
| 2 | **Where jobs run** — same host as amaca? | yes, same host for v1; remote-execution adapter is a v2 concern | adapter signature stays the same; ctx grows a `submit_to_cluster` later |
| 3 | **Single-user vs multi-user** | single-user, localhost, no auth in v1 | dictates whether jobs need an "owner_id" field now |
| 4 | **File handling cap** | 100 MB per file, files older than 30 d auto-deleted | persistent storage size; nice-to-have, can be added later |
| 5 | **Frontend framework** | SvelteKit (recommended) | switching cost increases as we write components |
| 6 | **Backend language constraint** | Python (matches your other work) | rules out e.g. a Rust core; can host adapters that *call* other-language binaries |
| 7 | **Live result streaming** | log stream yes; intermediate-result streaming no in v1 | UI complexity |
| 8 | **Persistence of past runs** | yes, keep last N=1000 per code | DB schema |

If any of those defaults are wrong, tell me which row and what you want
instead, and I'll revise the spec before we write code.

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

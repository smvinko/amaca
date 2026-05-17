# amaca

Web front end + plugin host for running scientific computing codes
through a browser. Codes plug in via a thin adapter contract; the
framework handles auth, job lifecycle, validation, and result display.

See [SPEC.md](SPEC.md) for the design.

## Setup: amaca + CCFLY (install & reinstall)

**`./scripts/setup.sh` is the canonical path for both first install
and every reinstall** — new machine, after a `git pull`, or after a
CCFLY pin bump. It's idempotent: just re-run it. Don't hand-roll the
install; the manual sequence in the appendix exists only for debugging
or a bespoke layout, not as a parallel "supported" path.

`./scripts/dev.sh --frontend` runs the stack.

From nothing to a running stack with the CCFLY atomic-kinetics code
plugged in:

### How the pieces fit

Three Git repos, **one shared Python virtualenv**:

| Repo | What it is |
|------|------------|
| `amaca` | this repo — API + job host + Svelte UI |
| `amaca-ccfly` | the thin adapter that registers CCFLY as an `amaca.codes` plugin |
| `ccfly-v2` | the CCFLY C++/SWIG code — **always pulled from GitHub at the pinned tag** into a script-managed cache, built there; never a working clone |

> **Why a build step at all:** CCFLY is a compiled C++/SWIG extension
> and its packaging ships no built artifact, so `pip install
> git+…@tag` alone gives an importable-but-broken `ccfly` (no
> `_libccfly.so`). The tagged source must be cloned and CMake-built.
> `scripts/setup.sh` does exactly that, into `~/.cache/amaca/ccfly-v2`,
> so your own ccfly hacking clone (if any) is irrelevant and untouched.
> The pinned tag is read straight from `amaca-ccfly/pyproject.toml`, so
> it can never drift from this README.

### 0. System prerequisites

Python **3.12+** (3.13 recommended), a C/C++/Fortran toolchain for the
CCFLY build, Node **≥ 20.19** (Vite 8) for the UI, and Git.

**macOS** (Homebrew):
```sh
brew install python@3.13 cmake ninja swig gcc suite-sparse node git
```
**Debian/Ubuntu**:
```sh
sudo apt-get update && sudo apt-get install -y \
  python3.13 python3.13-venv cmake ninja-build swig \
  gcc-13 g++-13 gfortran-13 libsqlite3-dev nodejs npm git
```
SUNDIALS/CVODE is **vendored** by the CCFLY build — do not install it
system-wide. SuiteSparse/KLU is optional (only the
`analytical_sparse_klu` solver path needs it; defaults don't). You can
skip this step and pass `--system-deps` to `setup.sh` to let CCFLY's
own installer offer to install the toolchain.

### 1. Get amaca + run setup

```sh
mkdir -p ~/src && cd ~/src
git clone https://github.com/smvinko/amaca.git
cd amaca
./scripts/setup.sh            # add --system-deps to also install the toolchain
```
`setup.sh` is idempotent (safe to re-run after a pull or a pin bump).
It clones `amaca-ccfly` next to `amaca` if absent, reads the pinned
ccfly tag, creates the venv at `~/.venvs/amaca-dev`, fetches +
CMake-builds CCFLY from GitHub at that tag, then installs amaca and the
adapter in the correct order. First run takes a few minutes (vendored
SUNDIALS). It ends by verifying `amaca codes: ['ccfly']`.

Override anything via env: `VENV`, `PYTHON`, `AMACA_CCFLY_DIR`,
`CCFLY_SRC` (see `./scripts/setup.sh --help`).

### 2. Run the stack

```sh
./scripts/dev.sh --frontend
```
Backend on `http://127.0.0.1:8000`, UI on **http://localhost:5173**
(use `localhost`, not `127.0.0.1` — Vite binds IPv6 `[::1]`). `Ctrl-C`
stops both. Backend-only: omit `--frontend`. See `--help` for env
overrides (`AMACA_DATA_DIR`, `AMACA_SESSION_SECRET`, `AMACA_PORT`,
`AMACA_CORES_PER_JOB`, `AMACA_MAX_CONCURRENT_JOBS`).

Log in with any username (dev-login is on), pick **CCFLY**, keep
defaults, **Run** → you should get a live `atomic kinetics` progress
bar then result figures. For a spectrum run set *Method* = UTA (see
the `.trb` note in Troubleshooting).

### Updating the CCFLY pin later

1. Bump `amaca-ccfly/pyproject.toml` → `ccfly @ git+…@<new tag>` (and
   the `v2.7.x` strings in `adapter.py`).
2. `./scripts/setup.sh` — re-fetches GitHub at the new tag, rebuilds,
   reinstalls.
3. `(cd ../amaca-ccfly && ~/.venvs/amaca-dev/bin/pytest -q)` — the
   suite includes a `SimulationConfig` schema-drift check.
4. Restart `./scripts/dev.sh` (plugin discovery runs once at startup).

The amaca↔CCFLY progress contract is purely the `@amaca:progress`
stderr sentinel parsed by `amaca.core.run_monitored`; CCFLY-internal
refactors need no amaca change as long as that line keeps printing.

### Troubleshooting

- **CCFLY missing from the UI** — adapter not in the venv the backend
  runs from, or the backend wasn't restarted after a setup re-run.
  Re-run `setup.sh`, restart `dev.sh`.
- **`initialization of _libccfly did not return an extension module`**
  — venv Python ≠ the Python CCFLY built against. Re-run `setup.sh`
  with a consistent `PYTHON`/`VENV`; on macOS ensure conda isn't
  shadowing Homebrew Python.
- **Adapter shows the wrong CCFLY version** — harmless stale editable
  `dist-info`; the adapter reads `ccfly/version.py` directly so it
  self-corrects. Restart `dev.sh` to refresh the UI string.
- **Spectrum runs produce no spectrum** — CCFLY's spectroscopy needs
  `.trb` atomic-data files that are **not** in Git (too large). Place
  them manually next to the run's data path; ask Sam. The default
  kinetics-only path (Method = off) needs no `.trb`.

### Appendix: what `setup.sh` does (manual equivalent)

For debugging or a bespoke layout. `$VENV` = `~/.venvs/amaca-dev`.

```sh
# 0. prerequisites: see step 0 above.

# 1. venv (one specific Python >=3.12, used for BOTH the venv and the
#    CCFLY build, or you get an _libccfly ABI-mismatch at import).
python3.13 -m venv "$VENV" && "$VENV/bin/pip" install -U pip

# 2. CCFLY from GitHub at the pinned tag, into a managed cache.
PIN=$(sed -n 's/.*ccfly-v2\.git@\([^"#]*\).*/\1/p' \
        ~/src/amaca-ccfly/pyproject.toml | head -n1)
git clone https://github.com/smvinko/ccfly-v2.git ~/.cache/amaca/ccfly-v2
git -C ~/.cache/amaca/ccfly-v2 checkout -f "$PIN"
( cd ~/.cache/amaca/ccfly-v2 \
  && CCFLY_PYTHON="$VENV/bin/python" ./install.sh --no-deps --no-pipx )
"$VENV/bin/pip" install -e ~/.cache/amaca/ccfly-v2      # packages the built .so

# 3. amaca, then the adapter. --no-deps is REQUIRED: it stops pip
#    re-resolving the ccfly git pin and overwriting the built install.
"$VENV/bin/pip" install -e "~/src/amaca[api,workers,dev]"
"$VENV/bin/pip" install -e ~/src/amaca-ccfly --no-deps
"$VENV/bin/pip" install "pyyaml>=6.0" "pandas>=2.0"

# 4. run
cd ~/src/amaca
AMACA_DEV_LOGIN=1 AMACA_DATA_DIR=~/.amaca-local \
  AMACA_SESSION_SECRET=local-dev-persistent-secret \
  "$VENV/bin/uvicorn" amaca.api.app:app --port 8000 --reload
cd frontend && npm install && npm run dev               # other terminal
```

| Env var | Purpose |
|---------|---------|
| `AMACA_DEV_LOGIN=1` | Dev-login form (any username, no GitHub OAuth). |
| `AMACA_DATA_DIR` | SQLite DB + job artifacts (outside the repo; survives restarts). Default `./data`. |
| `AMACA_SESSION_SECRET` | Fixed value ⇒ logins persist across restarts. |
| `AMACA_CORES_PER_JOB` | *(opt)* per-job CPU/thread budget. Default `min(8, host)`. |
| `AMACA_MAX_CONCURRENT_JOBS` | *(opt)* simultaneous running jobs. Default `host // cores_per_job`. |

## Test

```sh
pytest                       # unit + contract + api
pytest -m contract           # adapter contract tests only
```

## Writing a code adapter

amaca core ships with a single built-in adapter (`Demo`) used as a test
fixture. Every real code lives in its own package and plugs in via the
`amaca.codes` entry-point group — see [SPEC.md §2 "Plugin packages"](SPEC.md)
for the full contract. Skeleton:

```toml
# pyproject.toml
[project]
name = "amaca-yourcode"
dependencies = ["amaca", "yourcode @ git+https://github.com/you/yourcode.git@v1.2.3"]

[project.entry-points."amaca.codes"]
yourcode = "amaca_yourcode.adapter:YourCode"
```

```python
# amaca_yourcode/adapter.py
from amaca.core import Code, JobContext, register
from pydantic import BaseModel

class Inputs(BaseModel):  ...
class Outputs(BaseModel): ...

@register
class YourCode(Code):
    name = "yourcode"; title = "Your code"; version = "1.0.0"
    InputSchema = Inputs; OutputSchema = Outputs
    def run(self, inputs: Inputs, ctx: JobContext) -> Outputs: ...
```

`pip install -e amaca-yourcode/` and the adapter shows up in the amaca
UI on next start. The 5 generic contract tests in
`tests/test_adapter_contract.py` apply to every adapter — copy them
into your package to enforce them locally.

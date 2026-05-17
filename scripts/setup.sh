#!/usr/bin/env bash
# amaca + CCFLY one-shot dev setup. Idempotent — safe to re-run after a
# git pull or a ccfly pin bump (it re-fetches + rebuilds at the new tag).
#
# CCFLY is ALWAYS pulled from GitHub at the pinned tag into a
# script-managed cache — never a developer's local working clone, and
# never mutating one. (CCFLY is a compiled C++/SWIG extension whose
# build backend ships no compiled artifact, so `pip install git+…`
# alone yields an importable-but-broken package; we must clone the
# tagged source and run its CMake build. This script does that against
# a clean managed checkout so your own ccfly hacking clone, if any, is
# irrelevant and untouched.)
#
# What it does, in order:
#   1. locate (or clone) the amaca-ccfly adapter repo
#   2. read the pinned ccfly tag from amaca-ccfly/pyproject.toml
#      (single source of truth — never drifts from the README)
#   3. create the shared venv
#   4. clone/fetch ccfly-v2 from GitHub into the managed cache, check
#      out that tag, build the C++/SWIG ext (via ccfly's install.sh),
#      editable-install it into the venv
#   5. install amaca, then the amaca-ccfly adapter with --no-deps
#   6. verify the plugin is discoverable and points at real CCFLY
#
# It does NOT install system packages by default (cmake/swig/gcc/…).
# Pass --system-deps to let ccfly's install.sh offer to install them,
# or install them yourself first (see the README "System prerequisites").
#
# Config via env (all optional):
#   VENV            venv path            (default ~/.venvs/amaca-dev)
#   PYTHON          interpreter to seed   (default python3.13|3.12|python3)
#   AMACA_CCFLY_DIR amaca-ccfly checkout  (default ../amaca-ccfly)
#   CCFLY_SRC       managed ccfly cache   (default ~/.cache/amaca/ccfly-v2)
#
# Usage: scripts/setup.sh [--system-deps] [--help]

set -euo pipefail

DO_SYSTEM_DEPS=0
for arg in "$@"; do
  case "$arg" in
    --system-deps) DO_SYSTEM_DEPS=1 ;;
    -h|--help) sed -n '2,35p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

say() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

AMACA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT="$(dirname "$AMACA_DIR")"
VENV="${VENV:-$HOME/.venvs/amaca-dev}"
AMACA_CCFLY_DIR="${AMACA_CCFLY_DIR:-$PARENT/amaca-ccfly}"
CCFLY_SRC="${CCFLY_SRC:-$HOME/.cache/amaca/ccfly-v2}"
CCFLY_URL="https://github.com/smvinko/ccfly-v2.git"
AMACA_CCFLY_URL="https://github.com/smvinko/amaca-ccfly.git"

pick_python() {
  if [[ -n "${PYTHON:-}" ]]; then echo "$PYTHON"; return; fi
  for p in python3.13 python3.12 python3; do
    if command -v "$p" >/dev/null 2>&1 && \
       "$p" -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,12) else 1)'; then
      command -v "$p"; return
    fi
  done
  die "need Python >= 3.12 (set \$PYTHON or install python@3.13)"
}

say "amaca dev setup"
echo "    amaca:        $AMACA_DIR"
echo "    venv:         $VENV"
echo "    ccfly cache:  $CCFLY_SRC  (from $CCFLY_URL)"

# --- adapter repo (local clone is fine; only ccfly must be remote) ---
if [[ -d "$AMACA_CCFLY_DIR/.git" ]]; then
  echo "    amaca-ccfly:  $AMACA_CCFLY_DIR (existing)"
else
  say "cloning amaca-ccfly -> $AMACA_CCFLY_DIR"
  git clone "$AMACA_CCFLY_URL" "$AMACA_CCFLY_DIR"
fi

# --- the pinned ccfly tag = single source of truth -------------------
PIN_TAG="$(sed -n 's/.*ccfly-v2\.git@\([^"#[:space:]]*\).*/\1/p' \
            "$AMACA_CCFLY_DIR/pyproject.toml" | head -n1)"
[[ -n "$PIN_TAG" ]] || die "couldn't read the ccfly pin from $AMACA_CCFLY_DIR/pyproject.toml"
say "amaca-ccfly pins ccfly @ $PIN_TAG"

# --- venv ------------------------------------------------------------
if [[ ! -x "$VENV/bin/python" ]]; then
  PY="$(pick_python)"
  say "creating venv at $VENV ($("$PY" --version 2>&1))"
  "$PY" -m venv "$VENV"
fi
VPY="$VENV/bin/python"
"$VPY" -m pip install -q -U pip

# --- CCFLY: always from GitHub, into the managed cache ---------------
say "fetching CCFLY $PIN_TAG from GitHub"
if [[ -d "$CCFLY_SRC/.git" ]]; then
  git -C "$CCFLY_SRC" remote set-url origin "$CCFLY_URL"
  git -C "$CCFLY_SRC" fetch --tags --quiet origin
else
  mkdir -p "$(dirname "$CCFLY_SRC")"
  git clone --quiet "$CCFLY_URL" "$CCFLY_SRC"
fi
# Managed dir — we own it; hard-reset to the exact pinned tag so a
# rebuild artifact / SWIG regen never blocks the checkout.
git -C "$CCFLY_SRC" checkout --quiet -f "$PIN_TAG"
git -C "$CCFLY_SRC" reset --hard --quiet "$PIN_TAG"

say "building CCFLY $PIN_TAG (a few minutes the first time; vendored SUNDIALS)"
INSTALL_FLAGS=(--no-pipx)
(( DO_SYSTEM_DEPS )) || INSTALL_FLAGS+=(--no-deps)
( cd "$CCFLY_SRC" && CCFLY_PYTHON="$VPY" ./install.sh "${INSTALL_FLAGS[@]}" )
"$VPY" -m pip install -q -e "$CCFLY_SRC"

# --- amaca + adapter -------------------------------------------------
say "installing amaca (api, workers, dev)"
"$VPY" -m pip install -q -e "$AMACA_DIR[api,workers,dev]"

say "installing the amaca-ccfly adapter (--no-deps; keeps the built ccfly)"
"$VPY" -m pip install -q -e "$AMACA_CCFLY_DIR" --no-deps
"$VPY" -m pip install -q "pyyaml>=6.0" "pandas>=2.0" \
                         "pytest>=8" "pytest-cov>=5" "ruff>=0.6"

# --- verify ----------------------------------------------------------
say "verifying"
"$VPY" - <<'PY'
import ccfly, ccfly.version as v
from ccfly import SimulationConfig                       # built extension
from amaca.core import load_entry_points, all_codes
load_entry_points()
codes = sorted(c.name for c in all_codes())
print(f"    ccfly {v.get_version()}  |  amaca codes: {codes}")
assert "ccfly" in codes, "ccfly adapter not discoverable"
PY

cat <<EOF

==> Done. Start the stack with:

      scripts/dev.sh --frontend

    (or run backend / frontend separately — see the README).
EOF

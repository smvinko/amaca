# amaca

Web front end + plugin host for running scientific computing codes
through a browser. Codes plug in via a thin adapter contract; the
framework handles auth, job lifecycle, validation, and result display.

See [SPEC.md](SPEC.md) for the design.

## Status

Early scaffolding. See [SPEC.md §9](SPEC.md#9-what-id-build-first-once-spec-is-approved)
for the build order. The first end-to-end milestone is the bundled
`demo` adapter exercising the API and SPA without needing a real code
plugged in.

## Install (dev)

```sh
brew install python@3.14
python3.14 -m venv ~/.venvs/amaca-dev
source ~/.venvs/amaca-dev/bin/activate
pip install -e ".[api,workers,dev]"
```

## Test

```sh
pytest                       # unit + contract + api
pytest -m contract           # adapter contract tests only
```

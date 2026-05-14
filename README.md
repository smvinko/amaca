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

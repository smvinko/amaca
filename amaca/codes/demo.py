"""Demo adapter — exercises every required moving part of the framework.

Purpose:
- Lets the framework be fully tested end-to-end before any real code is
  wired in. The contract tests and the API/e2e tests all use this as a
  fixture.
- Exemplifies how a real adapter is written: one ``InputSchema``, one
  ``OutputSchema``, one ``run`` method, registered with ``@register``.

The "computation" is a parametric waveform plus a configurable sleep so
the async pipeline can be exercised without depending on a heavy
external code.
"""
from __future__ import annotations

import math
import time
from typing import Literal

from pydantic import BaseModel, Field

from amaca.core import Code, JobContext, register


class DemoInputs(BaseModel):
    n_points: int = Field(
        default=20, ge=2, le=10_000,
        description="Number of points sampled in [0, 2π]."
    )
    amplitude: float = Field(
        default=1.0, gt=0.0,
        description="Multiplier on the output waveform."
    )
    label: str = Field(
        default="demo run", min_length=1, max_length=80,
        description="Free-text label echoed in the output."
    )
    waveform: Literal["sine", "cosine", "square"] = Field(
        default="sine",
        description="Function evaluated at each sample point."
    )
    sleep_s: float = Field(
        default=0.0, ge=0.0, le=30.0,
        description="Pretend computation time (seconds)."
    )


class DemoOutputs(BaseModel):
    label: str
    n_points: int
    waveform: Literal["sine", "cosine", "square"]
    x: list[float]
    y: list[float]
    rms: float


_WAVEFORMS = {
    "sine":   math.sin,
    "cosine": math.cos,
    "square": lambda v: 1.0 if math.sin(v) >= 0 else -1.0,
}


@register
class Demo(Code):
    name = "demo"
    title = "Demo (built-in test adapter)"
    version = "0.1.0"

    InputSchema = DemoInputs
    OutputSchema = DemoOutputs

    def run(self, inputs: DemoInputs, ctx: JobContext) -> DemoOutputs:
        # Honour any cancellation that landed between submission and dispatch.
        if ctx.check_cancelled():
            ctx.log("demo: cancelled before start")
            raise RuntimeError("cancelled")
        ctx.log(f"demo: starting with {inputs.n_points} points, "
                f"waveform={inputs.waveform!r}, sleep={inputs.sleep_s}s")

        # Sleep in small slices so cancellation is responsive — and
        # report progress each slice (also exercises the ctx.progress
        # contract for the framework's tests).
        slept = 0.0
        slice_s = 0.05
        while slept < inputs.sleep_s:
            if ctx.check_cancelled():
                ctx.log("demo: cancelled by user")
                raise RuntimeError("cancelled")
            chunk = min(slice_s, inputs.sleep_s - slept)
            time.sleep(chunk)
            slept += chunk
            ctx.progress(slept / inputs.sleep_s, f"{slept:.2f}/{inputs.sleep_s:.2f} s")

        fn = _WAVEFORMS[inputs.waveform]
        xs = [i / (inputs.n_points - 1) * 2 * math.pi for i in range(inputs.n_points)]
        ys = [inputs.amplitude * fn(x) for x in xs]
        rms = math.sqrt(sum(y * y for y in ys) / len(ys))

        ctx.log(f"demo: produced {len(ys)} points, rms={rms:.6f}")
        return DemoOutputs(
            label=inputs.label,
            n_points=inputs.n_points,
            waveform=inputs.waveform,
            x=xs,
            y=ys,
            rms=rms,
        )

    def estimate_cost(self, inputs: DemoInputs) -> dict[str, str]:
        return {"time": f"≈ {inputs.sleep_s:.1f} s", "memory": "trivial"}

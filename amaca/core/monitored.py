"""Run a code as a subprocess with live progress + log bridging.

The standard way for an adapter to drive a long-running / blocking /
non-Python code: spawn it out-of-process and let amaca relay its
output. Running out-of-process is what makes progress observable at
all (an in-process native call can hold the GIL and freeze the
worker), and it also makes cancellation and crash isolation work.

Progress wire-format (the cross-code contract): the child emits, on
stdout (or stderr), single lines of the form::

    @amaca:progress {"phase": "kinetics", "step": 123, "total": 1000,
                      "message": "...", "fraction": 0.123}

All fields optional; ``fraction`` defaults to ``step/total``. Every
other output line is forwarded verbatim to the job log.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from .types import JobContext

SENTINEL = "@amaca:progress"


def run_monitored(
    argv: Sequence[str],
    ctx: JobContext,
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    sentinel: str = SENTINEL,
    poll_s: float = 0.2,
    cancel_grace_s: float = 5.0,
) -> int:
    """Spawn ``argv``, stream its output to the job, return its exit code.

    - stdout+stderr lines starting with ``sentinel`` are parsed as a
      JSON progress payload and forwarded to ``ctx.progress``; all
      other lines go to ``ctx.log``.
    - ``ctx.check_cancelled()`` is polled; on cancel the child is sent
      SIGTERM (then SIGKILL after ``cancel_grace_s``) and
      ``RuntimeError("cancelled")`` is raised (the runner maps that to
      a CANCELLED job).
    - A non-zero exit raises ``RuntimeError`` with the tail of output.
    """
    proc = subprocess.Popen(
        [str(a) for a in argv],
        cwd=str(cwd) if cwd is not None else None,
        env=dict(env) if env is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # line-buffered
    )

    prefix = sentinel + " "
    tail: list[str] = []

    def _pump() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            if line.startswith(prefix):
                try:
                    d = json.loads(line[len(prefix):])
                except Exception:
                    ctx.log(line)  # malformed sentinel — keep it visible
                    continue
                ctx.progress(
                    d.get("fraction"),
                    str(d.get("message", "") or ""),
                    step=d.get("step"),
                    total=d.get("total"),
                    phase=d.get("phase"),
                )
            else:
                ctx.log(line)
                tail.append(line)
                if len(tail) > 25:
                    del tail[0]

    reader = threading.Thread(target=_pump, daemon=True)
    reader.start()

    cancelled = False
    while proc.poll() is None:
        if ctx.check_cancelled():
            cancelled = True
            proc.terminate()
            try:
                proc.wait(timeout=cancel_grace_s)
            except subprocess.TimeoutExpired:
                proc.kill()
            break
        time.sleep(poll_s)

    proc.wait()
    reader.join(timeout=cancel_grace_s)

    if cancelled:
        raise RuntimeError("cancelled")
    if proc.returncode != 0:
        raise RuntimeError(
            f"{argv[0]} exited with code {proc.returncode}\n"
            + "\n".join(tail[-25:])
        )
    return 0

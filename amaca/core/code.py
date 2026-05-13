"""The ``Code`` base class — the adapter contract for every plugged-in code."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from .types import JobContext


class Code(ABC):
    """Base class every code adapter inherits from.

    Concrete subclasses must set ``name``, ``title``, ``InputSchema``,
    ``OutputSchema`` and implement ``run(...)``. The class-init hook
    catches missing required attributes at definition time rather than
    at first use, so a misshapen adapter fails loudly the moment it is
    imported.
    """
    name: ClassVar[str]
    title: ClassVar[str]
    version: ClassVar[str] = "0.1.0"

    InputSchema: ClassVar[type[BaseModel]]
    OutputSchema: ClassVar[type[BaseModel]]

    @abstractmethod
    def run(self, inputs: BaseModel, ctx: JobContext) -> BaseModel:
        """Execute the code synchronously.

        ``inputs`` is an already-validated instance of ``InputSchema``.
        Return an ``OutputSchema`` instance on success, or raise.

        The runner translates exceptions into a FAILED job; an explicit
        ``RuntimeError("cancelled")`` after ``ctx.check_cancelled()``
        becomes CANCELLED instead.

        Implementations should call ``ctx.check_cancelled()`` at the
        top of the function (in case the user cancelled between
        submission and dispatch), and again inside any long-running
        loops to keep cancellations responsive.
        """

    def estimate_cost(self, inputs: BaseModel) -> dict[str, str] | None:
        """Optional rough cost hint shown in the UI before submission.

        Return e.g. ``{"time": "1–5 min", "memory": "<1 GB"}`` or None.
        Default: no hint.
        """
        return None

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # only validate concrete subclasses
        if getattr(cls, "__abstractmethods__", None):
            return
        required = ("name", "title", "InputSchema", "OutputSchema")
        missing = [attr for attr in required if attr not in cls.__dict__ and not _attr_inherited(cls, attr)]
        if missing:
            raise TypeError(
                f"{cls.__name__} is missing required Code attrs: {missing}"
            )
        if not issubclass(cls.InputSchema, BaseModel):
            raise TypeError(f"{cls.__name__}.InputSchema must subclass pydantic.BaseModel")
        if not issubclass(cls.OutputSchema, BaseModel):
            raise TypeError(f"{cls.__name__}.OutputSchema must subclass pydantic.BaseModel")


def _attr_inherited(cls: type, attr: str) -> bool:
    for base in cls.__mro__[1:]:
        if attr in base.__dict__:
            return True
    return False

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from ...reasoning.models import TestStep


@dataclass
class StepResult:
    step_number: int
    success: bool
    raw_output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Skill(ABC):
    @abstractmethod
    async def execute(self, step: TestStep) -> StepResult:
        ...

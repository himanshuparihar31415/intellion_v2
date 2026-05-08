"""
FindingClassifier: classifies each StepResult into confirmed / logic_deviation / discovery.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..reasoning.models import StepType, TestStep
from .skills.base import StepResult


class FindingType(StrEnum):
    CONFIRMED = "confirmed"
    LOGIC_DEVIATION = "logic_deviation"
    DISCOVERY = "discovery"


@dataclass
class Finding:
    step_number: int
    finding_type: FindingType
    description: str
    raw_output: dict[str, Any]
    node_ids_affected: list


def classify(step: TestStep, result: StepResult) -> Finding:
    if not result.success:
        if step.step_type == StepType.DISCOVER:
            return Finding(
                step_number=step.step_number,
                finding_type=FindingType.DISCOVERY,
                description=f"Discovered: {result.error or 'unexpected behavior during discovery'}",
                raw_output=result.raw_output,
                node_ids_affected=step.node_ids,
            )
        return Finding(
            step_number=step.step_number,
            finding_type=FindingType.LOGIC_DEVIATION,
            description=f"Logic deviation: {result.error or 'step failed'}",
            raw_output=result.raw_output,
            node_ids_affected=step.node_ids,
        )

    # Success path
    observations = result.raw_output.get("observations", [])
    assertions_failed = any(
        not obs.get("passed", True) for obs in observations if obs.get("type", "").startswith("assert_")
    )

    if assertions_failed:
        return Finding(
            step_number=step.step_number,
            finding_type=FindingType.LOGIC_DEVIATION,
            description=f"Assertion failed on step {step.step_number}: {step.description}",
            raw_output=result.raw_output,
            node_ids_affected=step.node_ids,
        )

    if step.step_type == StepType.DISCOVER:
        return Finding(
            step_number=step.step_number,
            finding_type=FindingType.DISCOVERY,
            description=f"Discovery step completed: {step.description}",
            raw_output=result.raw_output,
            node_ids_affected=step.node_ids,
        )

    return Finding(
        step_number=step.step_number,
        finding_type=FindingType.CONFIRMED,
        description=f"Confirmed: {step.description}",
        raw_output=result.raw_output,
        node_ids_affected=step.node_ids,
    )

"""APISkill: executes HTTP API calls for API-type test steps."""
from __future__ import annotations

import httpx

from ...reasoning.models import TestStep
from .base import Skill, StepResult


class APISkill(Skill):
    def __init__(self, base_url: str, headers: dict | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}

    async def execute(self, step: TestStep) -> StepResult:
        # Step description format: "METHOD /path [body JSON]"
        parts = step.description.split(None, 2)
        if len(parts) < 2:
            return StepResult(
                step_number=step.step_number,
                success=False,
                error="APISkill: step description must start with METHOD /path",
            )

        method, path = parts[0].upper(), parts[1]
        body = None
        if len(parts) > 2:
            import json as _json
            try:
                body = _json.loads(parts[2])
            except Exception:
                pass

        url = self._base_url + path
        async with httpx.AsyncClient(headers=self._headers) as client:
            try:
                resp = await client.request(method, url, json=body, timeout=10.0)
                return StepResult(
                    step_number=step.step_number,
                    success=resp.status_code < 400,
                    raw_output={
                        "status": resp.status_code,
                        "url": url,
                        "response_preview": resp.text[:500],
                    },
                )
            except Exception as e:
                return StepResult(
                    step_number=step.step_number,
                    success=False,
                    error=str(e),
                )

"""
MissionRunner: executes a TestPlan step by step.
Implements the micro feedback loop: logic_deviation mid-mission
triggers abbreviated re-plan of remaining steps.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import asyncpg
from playwright.async_api import async_playwright

from ..reasoning.engine import ReasoningEngine
from ..reasoning.models import StepType, TestPlan
from .findings import Finding, FindingType, classify
from .skills.router import SkillRouter
from .sync import GraphSyncService


@dataclass
class MissionResult:
    mission_id: uuid.UUID
    session_id: uuid.UUID
    plan_id: uuid.UUID
    findings: list[Finding] = field(default_factory=list)
    sync_summary: dict = field(default_factory=dict)
    steps_executed: int = 0
    success: bool = True


class MissionRunner:
    def __init__(
        self,
        conn: asyncpg.Connection,
        intellion_id: uuid.UUID,
        session_id: uuid.UUID,
        target_url: str,
    ) -> None:
        self._conn = conn
        self._intellion_id = intellion_id
        self._session_id = session_id
        self._target_url = target_url

    async def run(self, plan: TestPlan) -> MissionResult:
        mission_id = uuid.uuid4()
        findings: list[Finding] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            router = SkillRouter(page, self._target_url)

            try:
                remaining_steps = list(plan.steps)
                while remaining_steps:
                    step = remaining_steps.pop(0)
                    skill = router.route(step)
                    result = await skill.execute(step)
                    finding = classify(step, result)
                    findings.append(finding)

                    # Micro feedback loop: re-plan on logic deviation
                    if finding.finding_type == FindingType.LOGIC_DEVIATION and remaining_steps:
                        engine = ReasoningEngine(self._conn, self._session_id)
                        new_result = await engine.reason(self._intellion_id, plan.task_description)
                        # Replace remaining steps with updated plan (steps 4+5 only — already scoped)
                        remaining_steps = [
                            s for s in new_result.plan.steps
                            if s.step_type in (StepType.VERIFY, StepType.DISCOVER)
                        ]
            finally:
                await context.close()
                await browser.close()

        # Sync findings back to graph
        sync_svc = GraphSyncService(self._conn, self._intellion_id, self._session_id)
        sync_summary = await sync_svc.sync(findings)

        return MissionResult(
            mission_id=mission_id,
            session_id=self._session_id,
            plan_id=plan.plan_id,
            findings=findings,
            sync_summary=sync_summary,
            steps_executed=len(findings),
            success=not any(f.finding_type == FindingType.LOGIC_DEVIATION for f in findings),
        )

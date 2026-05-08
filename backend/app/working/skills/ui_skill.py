"""
UISkill: Playwright execution in mission mode.
Execution mode: follows explicit selectors from the plan.
"""
from __future__ import annotations

import json

import anthropic
from playwright.async_api import Page

from ...config import settings
from ...reasoning.models import TestStep
from .base import Skill, StepResult

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM = (
    "You are executing a test step for a web application. "
    "Given a step description and current page state, generate the precise sequence of "
    "browser actions needed. Return structured actions, not prose."
)


class UISkill(Skill):
    def __init__(self, page: Page) -> None:
        self._page = page

    async def execute(self, step: TestStep) -> StepResult:
        actions = await self._plan_actions(step)
        observations: list[dict] = []

        for action in actions:
            try:
                obs = await self._run_action(action)
                observations.append(obs)
            except Exception as e:
                return StepResult(
                    step_number=step.step_number,
                    success=False,
                    raw_output={"actions_completed": observations, "failed_action": action},
                    error=str(e),
                )

        return StepResult(
            step_number=step.step_number,
            success=True,
            raw_output={
                "page_url": self._page.url,
                "observations": observations,
                "page_title": await self._page.title(),
            },
        )

    async def _plan_actions(self, step: TestStep) -> list[dict]:
        dom_summary = await self._page.evaluate(
            """
            () => Array.from(document.querySelectorAll(
                'a, button, input, select, [role=button]'
            )).slice(0, 20).map(el => ({
                tag: el.tagName.toLowerCase(),
                id: el.id || null,
                text: (el.textContent || el.value || '').trim().slice(0, 60),
                type: el.type || null,
            }))
            """
        )

        tools = [
            {
                "name": "plan_actions",
                "description": "Plan browser actions for this test step",
                "input_schema": {
                    "type": "object",
                    "required": ["actions"],
                    "properties": {
                        "actions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["type"],
                                "properties": {
                                    "type": {"type": "string", "enum": ["navigate", "click", "fill", "assert_text", "assert_visible", "assert_url"]},
                                    "selector": {"type": "string"},
                                    "value": {"type": "string"},
                                    "url": {"type": "string"},
                                    "expected": {"type": "string"},
                                },
                            },
                        }
                    },
                },
            }
        ]

        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Step: {step.description}\n"
                        f"Step type: {step.step_type}\n"
                        f"Current URL: {self._page.url}\n"
                        f"Page elements: {json.dumps(dom_summary, indent=2)}"
                    ),
                }
            ],
            tools=tools,
            tool_choice={"type": "any"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "plan_actions":
                return block.input.get("actions", [])
        return []

    async def _run_action(self, action: dict) -> dict:
        action_type = action["type"]
        obs: dict = {"type": action_type, "success": False}

        if action_type == "navigate":
            await self._page.goto(action["url"], wait_until="networkidle", timeout=15000)
            obs.update({"url": self._page.url, "success": True})

        elif action_type == "click":
            await self._page.click(action["selector"], timeout=5000)
            await self._page.wait_for_load_state("networkidle", timeout=8000)
            obs.update({"selector": action["selector"], "success": True})

        elif action_type == "fill":
            await self._page.fill(action["selector"], action["value"], timeout=5000)
            obs.update({"selector": action["selector"], "success": True})

        elif action_type == "assert_text":
            content = await self._page.text_content(action["selector"], timeout=3000)
            passed = action.get("expected", "") in (content or "")
            obs.update({"selector": action["selector"], "actual": content, "passed": passed, "success": passed})

        elif action_type == "assert_visible":
            visible = await self._page.is_visible(action["selector"], timeout=3000)
            obs.update({"selector": action["selector"], "visible": visible, "success": visible})

        elif action_type == "assert_url":
            actual = self._page.url
            passed = action.get("expected", "") in actual
            obs.update({"actual": actual, "passed": passed, "success": passed})

        return obs

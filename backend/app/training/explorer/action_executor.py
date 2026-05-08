"""
Asks Claude to suggest the next action given the current page DOM and graph context.
Execution mode: follow explicit selectors. Exploration mode: Claude decides.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import anthropic
from playwright.async_api import Page

from ...config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM = (
    "You are an intelligent web exploration agent. "
    "Given the current page DOM summary and what the Intellion already knows about this page, "
    "suggest the single next action that would most expand knowledge of the application. "
    "Prefer untested interactions over re-testing known ones. "
    "Never navigate away from the app's origin domain."
)


@dataclass
class ActionSuggestion:
    action_type: str  # click | fill | navigate | observe
    selector: str | None
    value: str | None  # for fill actions
    target_url: str | None  # for navigate actions
    rationale: str


async def suggest_next_action(
    page: Page,
    known_node_summaries: list[str],
    visited_urls: set[str],
) -> ActionSuggestion | None:
    """Ask Claude for the next exploration action."""
    dom_summary = await page.evaluate(
        """
        () => {
            const interactive = Array.from(document.querySelectorAll(
                'a, button, input, select, textarea, [role=button], [onclick]'
            )).slice(0, 30);
            return interactive.map(el => ({
                tag: el.tagName.toLowerCase(),
                id: el.id || null,
                text: (el.textContent || el.value || '').trim().slice(0, 80),
                href: el.href || null,
                type: el.type || null,
                selector: el.id ? '#' + el.id : el.className ? '.' + el.className.split(' ')[0] : el.tagName.toLowerCase(),
            }));
        }
        """
    )

    context = {
        "current_url": page.url,
        "page_title": await page.title(),
        "interactive_elements": dom_summary,
        "visited_urls": list(visited_urls)[:20],
        "known_graph_nodes": known_node_summaries[:15],
    }

    tools = [
        {
            "name": "suggest_action",
            "description": "Suggest the next browser action",
            "input_schema": {
                "type": "object",
                "required": ["action_type", "rationale"],
                "properties": {
                    "action_type": {"type": "string", "enum": ["click", "fill", "navigate", "observe"]},
                    "selector": {"type": "string"},
                    "value": {"type": "string"},
                    "target_url": {"type": "string"},
                    "rationale": {"type": "string"},
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
                "content": "What should we explore next?\n\n" + json.dumps(context, indent=2),
            }
        ],
        tools=tools,
        tool_choice={"type": "any"},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "suggest_action":
            d = block.input
            return ActionSuggestion(
                action_type=d["action_type"],
                selector=d.get("selector"),
                value=d.get("value"),
                target_url=d.get("target_url"),
                rationale=d["rationale"],
            )
    return None


async def execute_action(page: Page, action: ActionSuggestion) -> bool:
    """Execute the suggested action. Returns True on success."""
    try:
        if action.action_type == "navigate" and action.target_url:
            await page.goto(action.target_url, wait_until="networkidle", timeout=15000)
        elif action.action_type == "click" and action.selector:
            await page.click(action.selector, timeout=5000)
            await page.wait_for_load_state("networkidle", timeout=10000)
        elif action.action_type == "fill" and action.selector and action.value:
            await page.fill(action.selector, action.value, timeout=5000)
        elif action.action_type == "observe":
            pass  # no browser action; just capture current state
        return True
    except Exception:
        return False

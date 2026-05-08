from __future__ import annotations
from playwright.async_api import Page
from ...reasoning.models import TestStep
from .base import Skill
from .ui_skill import UISkill
from .api_skill import APISkill


class SkillRouter:
    def __init__(self, page: Page, target_url: str) -> None:
        self._page = page
        self._target_url = target_url

    def route(self, step: TestStep) -> Skill:
        if step.skill_hint == "api":
            return APISkill(self._target_url)
        return UISkill(self._page)

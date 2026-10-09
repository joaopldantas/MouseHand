"""Executes controller actions on the real OS cursor via PyAutoGUI."""

from __future__ import annotations

from collections.abc import Iterable

import pyautogui

from .controller import Action, Click, MouseDown, MouseUp, MoveTo, Scroll


class MouseDriver:
    def __init__(self) -> None:
        pyautogui.PAUSE = 0
        # Fail-safe stays on: slamming the physical mouse into a screen corner
        # raises FailSafeException, which works as an emergency stop.
        pyautogui.FAILSAFE = True

    @property
    def screen_size(self) -> tuple[int, int]:
        width, height = pyautogui.size()
        return width, height

    def execute(self, actions: Iterable[Action]) -> None:
        for action in actions:
            if isinstance(action, MoveTo):
                pyautogui.moveTo(action.x, action.y, duration=0)
            elif isinstance(action, Click):
                pyautogui.click(button=action.button)
            elif isinstance(action, MouseDown):
                pyautogui.mouseDown()
            elif isinstance(action, MouseUp):
                pyautogui.mouseUp()
            elif isinstance(action, Scroll):
                pyautogui.scroll(action.amount)
            else:
                raise TypeError(f"Unknown action: {action!r}")

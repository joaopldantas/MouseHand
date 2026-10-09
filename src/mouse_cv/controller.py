"""Gesture state machine.

`GestureController` turns one observed hand per frame into a list of mouse
actions. It has no dependency on the camera, MediaPipe or PyAutoGUI, so it can
be unit tested with synthetic landmarks and a fake clock.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Optional, Union

from .config import Config
from .geometry import INDEX_TIP, THUMB_TIP, Landmark, clamp, distance, fingers_up, map_normalized


@dataclass(frozen=True)
class HandObservation:
    landmarks: Sequence[Landmark]
    gesture: Optional[str] = None
    gesture_score: float = 0.0


@dataclass(frozen=True)
class MoveTo:
    x: int
    y: int


@dataclass(frozen=True)
class Click:
    button: str = "left"


@dataclass(frozen=True)
class MouseDown:
    pass


@dataclass(frozen=True)
class MouseUp:
    pass


@dataclass(frozen=True)
class Scroll:
    amount: int


Action = Union[MoveTo, Click, MouseDown, MouseUp, Scroll]


@dataclass
class FrameResult:
    actions: list[Action] = field(default_factory=list)
    event: Optional[str] = None
    fingers: tuple[bool, ...] = ()


class GestureController:
    def __init__(self, config: Config, screen_size: tuple[int, int]) -> None:
        self.config = config
        self.screen_width, self.screen_height = screen_size
        self.cursor_x = self.screen_width / 2
        self.cursor_y = self.screen_height / 2

        self.pinch_active = False
        self.pinch_started_at = 0.0
        self.dragging = False
        self.scroll_mode = False
        # A single click is deferred until `double_click_gap` passes, so a
        # second pinch in that window can turn it into a right click instead.
        self.pending_click_at: Optional[float] = None
        self.last_click_at = -math.inf
        self.last_right_click_at = -math.inf
        self.last_scroll_at = -math.inf

    def update(self, hand: Optional[HandObservation], now: float) -> FrameResult:
        out = FrameResult()
        self._flush_pending_click(now, out)

        if hand is None:
            out.actions.extend(self.release())
            return out

        landmarks = hand.landmarks
        index_tip = landmarks[INDEX_TIP]
        out.fingers = fingers_up(landmarks)

        self._update_pinch(distance(landmarks[THUMB_TIP], index_tip), now, out)
        self._update_drag(now, out)
        self._update_right_click_gesture(hand, now, out)
        self._update_scroll(out.fingers, index_tip, now, out)
        self._update_cursor(index_tip, out)
        return out

    def release(self) -> list[Action]:
        """Reset transient state; returns a MouseUp if a drag was in progress."""
        self.pinch_active = False
        self.scroll_mode = False
        if self.dragging:
            self.dragging = False
            return [MouseUp()]
        return []

    def _flush_pending_click(self, now: float, out: FrameResult) -> None:
        if self.pending_click_at is not None and now - self.pending_click_at > self.config.double_click_gap:
            out.actions.append(Click())
            out.event = "Click"
            self.pending_click_at = None
            self.last_click_at = now

    def _update_pinch(self, dist: float, now: float, out: FrameResult) -> None:
        cfg = self.config
        threshold = cfg.pinch_end_dist if self.pinch_active else cfg.pinch_start_dist
        pinching = dist < threshold

        if pinching and not self.pinch_active:
            self.pinch_active = True
            self.pinch_started_at = now
        elif not pinching and self.pinch_active:
            self.pinch_active = False
            self._on_pinch_release(now - self.pinch_started_at, now, out)

    def _on_pinch_release(self, duration: float, now: float, out: FrameResult) -> None:
        cfg = self.config
        if self.dragging:
            out.actions.append(MouseUp())
            out.event = "Drop"
            self.dragging = False
            return

        is_tap = (
            cfg.pinch_debounce_time <= duration <= cfg.pinch_max_click_time
            and now - self.last_click_at >= cfg.click_cooldown
        )
        if not is_tap:
            return

        if self.pending_click_at is not None and (
            cfg.double_click_min <= now - self.pending_click_at <= cfg.double_click_gap
        ):
            out.actions.append(Click("right"))
            out.event = "Right click"
            self.pending_click_at = None
            self.last_click_at = now
        else:
            self.pending_click_at = now

    def _update_drag(self, now: float, out: FrameResult) -> None:
        cfg = self.config
        held_for = now - self.pinch_started_at
        if self.pinch_active and not self.dragging and held_for >= max(cfg.pinch_debounce_time, cfg.drag_hold_time):
            self.pending_click_at = None
            self.dragging = True
            out.actions.append(MouseDown())
            out.event = "Drag"

    def _update_right_click_gesture(self, hand: HandObservation, now: float, out: FrameResult) -> None:
        cfg = self.config
        if (
            hand.gesture == cfg.right_click_gesture
            and hand.gesture_score >= cfg.right_click_score
            and not self.pinch_active
            and not self.dragging
            and now - self.last_right_click_at >= cfg.right_click_cooldown
        ):
            out.actions.append(Click("right"))
            out.event = "Right click"
            self.pending_click_at = None
            self.last_right_click_at = now

    def _update_scroll(self, fingers: tuple[bool, ...], index_tip: Landmark, now: float, out: FrameResult) -> None:
        cfg = self.config
        self.scroll_mode = sum(fingers) == 4 and not self.pinch_active and not self.dragging
        if not self.scroll_mode:
            return

        if index_tip.y <= cfg.scroll_zone_top:
            direction = 1
        elif index_tip.y >= cfg.scroll_zone_bottom:
            direction = -1
        else:
            return

        if now - self.last_scroll_at >= cfg.scroll_cooldown:
            out.actions.append(Scroll(direction * cfg.scroll_step))
            out.event = "Scroll up" if direction > 0 else "Scroll down"
            self.last_scroll_at = now

    def _update_cursor(self, index_tip: Landmark, out: FrameResult) -> None:
        cfg = self.config
        can_move = not self.pinch_active or self.dragging
        if self.scroll_mode and not cfg.move_during_scroll:
            can_move = False
        if not can_move:
            return

        target_x = map_normalized(index_tip.x, cfg.move_x_min, cfg.move_x_max) * self.screen_width
        target_y = map_normalized(index_tip.y, cfg.move_y_min, cfg.move_y_max) * self.screen_height
        self.cursor_x += (target_x - self.cursor_x) * cfg.cursor_smoothing
        self.cursor_y += (target_y - self.cursor_y) * cfg.cursor_smoothing
        # Stay 1px away from the screen edges: PyAutoGUI's fail-safe aborts
        # whenever the cursor lands exactly on a corner.
        x = int(clamp(self.cursor_x, 1, self.screen_width - 2))
        y = int(clamp(self.cursor_y, 1, self.screen_height - 2))
        out.actions.append(MoveTo(x, y))

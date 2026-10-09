"""On-screen overlay drawn on top of the camera preview."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

import cv2

from .config import Config
from .controller import GestureController
from .geometry import HAND_CONNECTIONS, Landmark

FONT = cv2.FONT_HERSHEY_SIMPLEX
WHITE = (255, 255, 255)
GRAY = (160, 160, 160)
GREEN = (80, 220, 100)
YELLOW = (0, 220, 255)
CYAN = (255, 200, 0)


def _to_px(landmark: Landmark, width: int, height: int) -> tuple[int, int]:
    return int(landmark.x * width), int(landmark.y * height)


def draw_hand(frame, landmarks: Sequence[Landmark]) -> None:
    height, width = frame.shape[:2]
    points = [_to_px(lm, width, height) for lm in landmarks]
    for start, end in HAND_CONNECTIONS:
        cv2.line(frame, points[start], points[end], GRAY, 2, cv2.LINE_AA)
    for point in points:
        cv2.circle(frame, point, 4, GREEN, -1, cv2.LINE_AA)


def draw_move_zone(frame, config: Config) -> None:
    height, width = frame.shape[:2]
    top_left = (int(config.move_x_min * width), int(config.move_y_min * height))
    bottom_right = (int(config.move_x_max * width), int(config.move_y_max * height))
    cv2.rectangle(frame, top_left, bottom_right, GRAY, 1, cv2.LINE_AA)


def draw_status(
    frame,
    controller: GestureController,
    gesture: Optional[str],
    fingers: tuple[bool, ...],
    event: Optional[str],
) -> None:
    if controller.dragging:
        mode = "DRAG"
    elif controller.scroll_mode:
        mode = "SCROLL"
    elif controller.pinch_active:
        mode = "PINCH"
    else:
        mode = "MOVE"

    lines = [
        (f"Mode: {mode}", CYAN),
        (f"Gesture: {gesture or '-'}", WHITE),
        (f"Fingers up: {sum(fingers)}", WHITE),
    ]
    if event:
        lines.append((event, YELLOW))

    for i, (text, color) in enumerate(lines):
        y = 28 + 26 * i
        cv2.putText(frame, text, (12, y), FONT, 0.65, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, text, (12, y), FONT, 0.65, color, 2, cv2.LINE_AA)

    cv2.putText(frame, "q: quit", (12, frame.shape[0] - 12), FONT, 0.5, GRAY, 1, cv2.LINE_AA)

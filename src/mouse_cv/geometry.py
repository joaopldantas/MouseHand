"""Small geometry helpers over MediaPipe hand landmarks."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

# Landmark indices, see:
# https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker#models
THUMB_TIP = 4
INDEX_TIP = 8
FINGER_TIPS = (8, 12, 16, 20)  # index, middle, ring, pinky

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)  # fmt: skip


class Landmark(Protocol):
    x: float
    y: float


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def map_normalized(value: float, min_value: float, max_value: float) -> float:
    """Linearly map `value` from [min_value, max_value] to [0, 1], clamped."""
    if max_value <= min_value:
        return 0.5
    return clamp((value - min_value) / (max_value - min_value), 0.0, 1.0)


def distance(a: Landmark, b: Landmark) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def fingers_up(landmarks: Sequence[Landmark]) -> tuple[bool, ...]:
    """Return which of index, middle, ring and pinky are extended.

    A finger counts as extended when its tip is above its PIP joint
    (smaller y, since image coordinates grow downwards).
    """
    return tuple(landmarks[tip].y < landmarks[tip - 2].y for tip in FINGER_TIPS)

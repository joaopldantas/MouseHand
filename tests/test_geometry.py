from dataclasses import dataclass

import pytest

from mouse_cv.geometry import clamp, distance, fingers_up, map_normalized


@dataclass
class Point:
    x: float
    y: float


def test_clamp():
    assert clamp(5, 0, 1) == 1
    assert clamp(-5, 0, 1) == 0
    assert clamp(0.3, 0, 1) == 0.3


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.15, 0.0), (0.85, 1.0), (0.5, 0.5), (0.0, 0.0), (1.0, 1.0)],
)
def test_map_normalized(value, expected):
    assert map_normalized(value, 0.15, 0.85) == pytest.approx(expected)


def test_map_normalized_degenerate_range():
    assert map_normalized(0.3, 0.5, 0.5) == 0.5


def test_distance():
    assert distance(Point(0, 0), Point(3, 4)) == 5


def test_fingers_up():
    landmarks = [Point(0.5, 0.5) for _ in range(21)]
    landmarks[8] = Point(0.5, 0.2)  # index tip above its PIP joint
    landmarks[20] = Point(0.5, 0.2)  # pinky tip above its PIP joint
    assert fingers_up(landmarks) == (True, False, False, True)

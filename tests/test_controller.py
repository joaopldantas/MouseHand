from dataclasses import dataclass

import pytest

from mouse_cv.config import Config
from mouse_cv.controller import Click, GestureController, HandObservation, MouseDown, MouseUp, MoveTo, Scroll
from mouse_cv.geometry import FINGER_TIPS, INDEX_TIP, THUMB_TIP

SCREEN = (1000, 800)


@dataclass
class Point:
    x: float
    y: float


def make_hand(index=(0.5, 0.5), pinch=False, fingers=(True, False, False, False), gesture=None, score=0.0):
    """Build 21 synthetic landmarks with the given index position and finger state."""
    landmarks = [Point(0.5, 0.5) for _ in range(21)]
    for tip, up in zip(FINGER_TIPS, fingers):
        base_y = index[1] if tip == INDEX_TIP else 0.5
        landmarks[tip] = Point(index[0] if tip == INDEX_TIP else 0.5, base_y)
        landmarks[tip - 2] = Point(0.5, base_y + (0.05 if up else -0.05))
    thumb_offset = 0.01 if pinch else 0.2
    landmarks[THUMB_TIP] = Point(index[0] - thumb_offset, index[1])
    return HandObservation(landmarks, gesture, score)


class Clock:
    def __init__(self):
        self.now = 100.0

    def tick(self, seconds=0.0):
        self.now += seconds
        return self.now


@pytest.fixture
def ctrl():
    return GestureController(Config(), SCREEN)


@pytest.fixture
def clock():
    return Clock()


def non_move(actions):
    return [a for a in actions if not isinstance(a, MoveTo)]


def tap(ctrl, clock, hold=0.15):
    """Pinch and release; returns all non-move actions emitted."""
    actions = []
    actions += ctrl.update(make_hand(pinch=True), clock.tick(0.03)).actions
    actions += ctrl.update(make_hand(pinch=True), clock.tick(hold)).actions
    actions += ctrl.update(make_hand(), clock.tick(0.01)).actions
    return non_move(actions)


def test_short_pinch_clicks_after_double_click_window(ctrl, clock):
    assert tap(ctrl, clock) == []  # deferred while waiting for a possible second pinch
    result = ctrl.update(make_hand(), clock.tick(Config().double_click_gap + 0.01))
    assert Click("left") in result.actions
    assert result.event == "Click"


def test_two_quick_pinches_right_click(ctrl, clock):
    tap(ctrl, clock)
    clock.tick(0.2)
    assert tap(ctrl, clock) == [Click("right")]
    # The pending left click must have been consumed.
    assert non_move(ctrl.update(make_hand(), clock.tick(2.0)).actions) == []


def test_long_pinch_drags_and_drops(ctrl, clock):
    ctrl.update(make_hand(pinch=True), clock.tick(0.03))
    result = ctrl.update(make_hand(pinch=True), clock.tick(Config().drag_hold_time + 0.01))
    assert MouseDown() in result.actions
    assert ctrl.dragging

    # Cursor keeps following the hand while dragging.
    result = ctrl.update(make_hand(index=(0.8, 0.5), pinch=True), clock.tick(0.03))
    assert any(isinstance(a, MoveTo) for a in result.actions)

    result = ctrl.update(make_hand(), clock.tick(0.03))
    assert MouseUp() in result.actions
    assert result.event == "Drop"
    assert not ctrl.dragging


def test_losing_hand_mid_drag_releases_button(ctrl, clock):
    ctrl.update(make_hand(pinch=True), clock.tick(0.03))
    ctrl.update(make_hand(pinch=True), clock.tick(1.0))
    assert ctrl.dragging
    assert ctrl.update(None, clock.tick(0.03)).actions == [MouseUp()]
    assert not ctrl.dragging


def test_release_without_drag_is_noop(ctrl):
    assert ctrl.release() == []


def test_closed_fist_right_clicks_with_cooldown(ctrl, clock):
    fist = make_hand(fingers=(False,) * 4, gesture="Closed_Fist", score=0.9)
    assert Click("right") in ctrl.update(fist, clock.tick(0.03)).actions
    assert Click("right") not in ctrl.update(fist, clock.tick(0.1)).actions
    assert Click("right") in ctrl.update(fist, clock.tick(Config().right_click_cooldown)).actions


def test_low_confidence_fist_is_ignored(ctrl, clock):
    fist = make_hand(fingers=(False,) * 4, gesture="Closed_Fist", score=0.3)
    assert non_move(ctrl.update(fist, clock.tick(0.03)).actions) == []


@pytest.mark.parametrize(("y", "expected"), [(0.2, 1), (0.8, -1)])
def test_four_fingers_scroll(ctrl, clock, y, expected):
    result = ctrl.update(make_hand(index=(0.5, y), fingers=(True,) * 4), clock.tick(0.1))
    assert result.actions == [Scroll(expected * Config().scroll_step)]  # no cursor movement while scrolling


def test_four_fingers_in_neutral_zone_does_nothing(ctrl, clock):
    assert ctrl.update(make_hand(index=(0.5, 0.5), fingers=(True,) * 4), clock.tick(0.1)).actions == []


def test_cursor_never_reaches_screen_corner(ctrl, clock):
    for _ in range(200):
        result = ctrl.update(make_hand(index=(0.0, 0.0)), clock.tick(0.03))
    assert result.actions[-1] == MoveTo(1, 1)
    for _ in range(200):
        result = ctrl.update(make_hand(index=(1.0, 1.0)), clock.tick(0.03))
    assert result.actions[-1] == MoveTo(SCREEN[0] - 2, SCREEN[1] - 2)

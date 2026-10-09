"""Tunable parameters for gesture detection and cursor control.

All distances and positions are in MediaPipe normalized image coordinates
(0.0 to 1.0 on each axis); all times are in seconds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Region of the camera frame mapped onto the whole screen. Using a central
    # box means you can reach the screen edges without leaving the camera view.
    move_x_min: float = 0.15
    move_x_max: float = 0.85
    move_y_min: float = 0.15
    move_y_max: float = 0.85
    # Exponential smoothing factor (0 = frozen, 1 = no smoothing).
    cursor_smoothing: float = 0.25
    move_during_scroll: bool = False

    # Pinch uses hysteresis: it starts below `pinch_start_dist` and only ends
    # above `pinch_end_dist`, which avoids flickering around a single threshold.
    pinch_start_dist: float = 0.055
    pinch_end_dist: float = 0.075
    pinch_debounce_time: float = 0.06
    pinch_max_click_time: float = 0.45
    click_cooldown: float = 0.2
    double_click_min: float = 0.1
    double_click_gap: float = 0.5
    drag_hold_time: float = 0.45

    right_click_gesture: str = "Closed_Fist"
    right_click_score: float = 0.7
    right_click_cooldown: float = 0.8

    scroll_zone_top: float = 0.35
    scroll_zone_bottom: float = 0.65
    scroll_step: int = 90
    scroll_cooldown: float = 0.04

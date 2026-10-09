"""Camera loop: webcam -> MediaPipe gesture recognizer -> controller -> mouse."""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Sequence
from pathlib import Path
from threading import Lock
from typing import Optional

import cv2
from mediapipe import Image, ImageFormat
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

from . import hud
from .config import Config
from .controller import GestureController, HandObservation
from .mouse import MouseDriver

DEFAULT_MODEL_PATH = Path(__file__).parent / "models" / "gesture_recognizer.task"
WINDOW_NAME = "mouse_cv"
EVENT_DISPLAY_SECONDS = 0.8

log = logging.getLogger("mouse_cv")


class LatestResult:
    """Thread-safe holder for the most recent async recognizer result."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._value: Optional[mp_vision.GestureRecognizerResult] = None

    def set(self, result, _output_image, _timestamp_ms) -> None:
        with self._lock:
            self._value = result

    def get(self) -> Optional[mp_vision.GestureRecognizerResult]:
        with self._lock:
            return self._value


def to_observation(result: Optional[mp_vision.GestureRecognizerResult]) -> Optional[HandObservation]:
    if not result or not result.hand_landmarks:
        return None
    gesture, score = None, 0.0
    if result.gestures and result.gestures[0]:
        top = result.gestures[0][0]
        gesture, score = top.category_name, top.score
    return HandObservation(result.hand_landmarks[0], gesture, score)


def create_recognizer(model_path: Path, on_result: LatestResult) -> mp_vision.GestureRecognizer:
    options = mp_vision.GestureRecognizerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp_vision.RunningMode.LIVE_STREAM,
        num_hands=1,
        result_callback=on_result.set,
    )
    return mp_vision.GestureRecognizer.create_from_options(options)


def run(config: Config, camera_index: int, model_path: Path, show_preview: bool = True) -> int:
    if not model_path.is_file():
        log.error("Model file not found: %s", model_path)
        return 1

    mouse = MouseDriver()
    controller = GestureController(config, mouse.screen_size)
    latest = LatestResult()
    recognizer = create_recognizer(model_path, latest)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        log.error("Could not open camera %d (check camera permissions)", camera_index)
        recognizer.close()
        return 1

    log.info("Running. Press 'q' in the preview window (or Ctrl+C) to quit.")
    last_timestamp_ms = -1
    last_event: Optional[str] = None
    last_event_at = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                log.error("Could not read frame from camera")
                return 1

            frame = cv2.flip(frame, 1)  # mirror, so moving right moves the cursor right
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # LIVE_STREAM mode requires strictly increasing timestamps.
            timestamp_ms = max(int(time.monotonic() * 1000), last_timestamp_ms + 1)
            last_timestamp_ms = timestamp_ms
            recognizer.recognize_async(Image(image_format=ImageFormat.SRGB, data=rgb), timestamp_ms)

            now = time.monotonic()
            hand = to_observation(latest.get())
            result = controller.update(hand, now)
            mouse.execute(result.actions)

            if result.event:
                last_event, last_event_at = result.event, now

            if show_preview:
                hud.draw_move_zone(frame, config)
                if hand:
                    hud.draw_hand(frame, hand.landmarks)
                event = last_event if now - last_event_at < EVENT_DISPLAY_SECONDS else None
                hud.draw_status(frame, controller, hand.gesture if hand else None, result.fingers, event)
                cv2.imshow(WINDOW_NAME, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    return 0
    except KeyboardInterrupt:
        return 0
    finally:
        # Never leave the mouse button held down if we exit mid-drag.
        mouse.execute(controller.release())
        cap.release()
        recognizer.close()
        cv2.destroyAllWindows()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="mouse-cv", description="Control your mouse with hand gestures.")
    parser.add_argument("-c", "--camera", type=int, default=0, help="camera index (default: 0)")
    parser.add_argument("-m", "--model", type=Path, default=DEFAULT_MODEL_PATH, help="path to a .task gesture model")
    parser.add_argument("--no-preview", action="store_true", help="run without the camera preview window")
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")
    return run(Config(), args.camera, args.model, show_preview=not args.no_preview)

import time
import pyautogui
import cv2
import math
from threading import Lock
from mediapipe import Image, ImageFormat
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

pyautogui.PAUSE = 0

screen_width, screen_height = pyautogui.size()
print("\n hand mouse control")

MODEL_PATH = "gesture_recognizer.task"

MOVE_X_MIN = 0.15
MOVE_X_MAX = 0.85
MOVE_Y_MIN = 0.15
MOVE_Y_MAX = 0.85
CURSOR_SMOOTHING = 0.25
MOVE_DURING_SCROLL = False

PINCH_START_DIST = 0.055
PINCH_END_DIST = 0.075
PINCH_DEBOUNCE_TIME = 0.06
PINCH_MAX_CLICK_TIME = 0.45
CLICK_COOLDOWN = 0.2
DOUBLE_CLICK_MIN = 0.1
DOUBLE_CLICK_GAP = 0.5
DRAG_HOLD_TIME = 0.45

RIGHT_CLICK_GESTURE = "Closed_Fist"
RIGHT_CLICK_SCORE = 0.7
RIGHT_CLICK_COOLDOWN = 0.8

SCROLL_ZONE_TOP = 0.35
SCROLL_ZONE_BOTTOM = 0.65
SCROLL_STEP = 90
SCROLL_COOLDOWN = 0.04


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def map_normalized(value, min_value, max_value):
    if max_value <= min_value:
        return 0.5
    return clamp((value - min_value) / (max_value - min_value), 0.0, 1.0)


def draw_hand_landmarks(image, hand_landmarks_list):
    for hand_landmarks in hand_landmarks_list:
        mp_vision.drawing_utils.draw_landmarks(
            image,
            hand_landmarks,
            mp_vision.HandLandmarksConnections.HAND_CONNECTIONS,
        )


def get_fingers_up(hand_landmarks):
    tips = (8, 12, 16, 20)
    return [
        1 if hand_landmarks[tip].y < hand_landmarks[tip - 2].y else 0
        for tip in tips
    ]


def main():
    result_lock = Lock()
    latest_result = None
    # gestures time control
    last_click_action = 0.0
    pending_click_time = 0.0
    pinch_active = False
    pinch_started_at = 0.0
    dragging = False
    last_right_click_time = 0.0
    scroll_mode = False
    last_scroll_time = 0.0
    cursor_x = screen_width / 2
    cursor_y = screen_height / 2

    def result_callback(result, _output_image, _timestamp_ms):
        nonlocal latest_result
        with result_lock:
            latest_result = result

    base_options = mp_tasks.BaseOptions(model_asset_path=MODEL_PATH)
    options = mp_vision.GestureRecognizerOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.LIVE_STREAM,
        num_hands=1,
        result_callback=result_callback,
    )
    recognizer = mp_vision.GestureRecognizer.create_from_options(options)

    cap = cv2.VideoCapture(0)  # camera padrao do note
    if not cap.isOpened():
        print("Nao foi possivel abrir a camera")
        recognizer.close()
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Nao foi possivel capturar o frame")
                break

            frame = cv2.flip(frame, 1)  # espelha a imagem
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # converte a imagem para RGB
            mp_image = Image(image_format=ImageFormat.SRGB, data=rgb)
            timestamp_ms = int(time.monotonic() * 1000)
            recognizer.recognize_async(mp_image, timestamp_ms)

            with result_lock:
                result = latest_result

            now = time.time()
            action_text = None
            if pending_click_time > 0 and now - pending_click_time > DOUBLE_CLICK_GAP:
                pyautogui.click()
                pending_click_time = 0.0
                last_click_action = now
                action_text = "Single Click"

            if result and result.hand_landmarks:
                draw_hand_landmarks(frame, result.hand_landmarks)
                for i, hand_landmarks in enumerate(result.hand_landmarks):
                    fingers = get_fingers_up(hand_landmarks)
                    count = sum(fingers)
                    cv2.putText(
                        frame,
                        f"Fingers: {count}",
                        (10, 60 + 20 * i),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 255),
                        2,
                    )

                    thumb_tip = hand_landmarks[4]
                    index_tip = hand_landmarks[8]

                    dist = math.hypot(thumb_tip.x - index_tip.x, thumb_tip.y - index_tip.y)
                    if pinch_active:
                        pinch_now = dist < PINCH_END_DIST
                    else:
                        pinch_now = dist < PINCH_START_DIST

                    if pinch_now and not pinch_active:
                        pinch_active = True
                        pinch_started_at = now
                    elif not pinch_now and pinch_active:
                        pinch_duration = now - pinch_started_at
                        if dragging:
                            pyautogui.mouseUp()
                            dragging = False
                            action_text = "Drop"
                        else:
                            can_click = (
                                pinch_duration >= PINCH_DEBOUNCE_TIME
                                and pinch_duration <= PINCH_MAX_CLICK_TIME
                                and now - last_click_action >= CLICK_COOLDOWN
                            )
                            if can_click:
                                if pending_click_time > 0:
                                    click_gap = now - pending_click_time
                                    if DOUBLE_CLICK_MIN <= click_gap <= DOUBLE_CLICK_GAP:
                                        pyautogui.click(button="right")
                                        pending_click_time = 0.0
                                        last_click_action = now
                                        action_text = "Right Click"
                                    else:
                                        pending_click_time = now
                                else:
                                    pending_click_time = now
                        pinch_active = False

                    pinch_confirmed = pinch_active and (now - pinch_started_at >= PINCH_DEBOUNCE_TIME)
                    if pinch_confirmed and not dragging and now - pinch_started_at >= DRAG_HOLD_TIME:
                        if pending_click_time > 0:
                            pending_click_time = 0.0
                        pyautogui.mouseDown()
                        dragging = True
                        action_text = "Drag"

                    if result.gestures and i < len(result.gestures) and result.gestures[i]:
                        gesture = result.gestures[i][0]
                        if (
                            gesture.category_name == RIGHT_CLICK_GESTURE
                            and gesture.score >= RIGHT_CLICK_SCORE
                            and not pinch_active
                            and not dragging
                            and now - last_right_click_time >= RIGHT_CLICK_COOLDOWN
                        ):
                            pyautogui.click(button="right")
                            if pending_click_time > 0:
                                pending_click_time = 0.0
                            last_right_click_time = now
                            action_text = "Right Click"

                    scroll_mode = sum(fingers) == 4 and not pinch_active and not dragging
                    if scroll_mode:
                        scroll_dir = 0
                        if index_tip.y <= SCROLL_ZONE_TOP:
                            scroll_dir = 1
                        elif index_tip.y >= SCROLL_ZONE_BOTTOM:
                            scroll_dir = -1
                        if scroll_dir != 0 and now - last_scroll_time >= SCROLL_COOLDOWN:
                            pyautogui.scroll(scroll_dir * SCROLL_STEP)
                            last_scroll_time = now
                            if scroll_dir > 0:
                                cv2.putText(
                                    frame,
                                    "Scroll Up",
                                    (10, 90),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    1,
                                    (0, 255, 0),
                                    2,
                                )
                            else:
                                cv2.putText(
                                    frame,
                                    "Scroll Down",
                                    (10, 90),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    1,
                                    (0, 0, 255),
                                    2,
                                )

                    can_move = (not pinch_active) or dragging
                    if scroll_mode and not MOVE_DURING_SCROLL:
                        can_move = False
                    if can_move:
                        norm_x = map_normalized(index_tip.x, MOVE_X_MIN, MOVE_X_MAX)
                        norm_y = map_normalized(index_tip.y, MOVE_Y_MIN, MOVE_Y_MAX)
                        target_x = norm_x * screen_width
                        target_y = norm_y * screen_height
                        cursor_x += (target_x - cursor_x) * CURSOR_SMOOTHING
                        cursor_y += (target_y - cursor_y) * CURSOR_SMOOTHING
                        pyautogui.moveTo(int(cursor_x), int(cursor_y), duration=0)

                    cv2.putText(
                        frame,
                        f"Dedos: {fingers}",
                        (10, 80),  # Posição do texto na tela
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 0, 0),
                        2,
                    )

                if action_text:
                    cv2.putText(
                        frame,
                        action_text,
                        (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (255, 255, 0),
                        2,
                    )
            else:
                if dragging:
                    pyautogui.mouseUp()
                    dragging = False
                pinch_active = False
                scroll_mode = False
                    
            if result and result.gestures:
                for i, gesture_list in enumerate(result.gestures):
                    if not gesture_list:
                        continue
                    gesture = gesture_list[0]
                    text = f"{gesture.category_name} ({gesture.score:.2f})"
                    cv2.putText(
                        frame,
                        text,
                        (10, 30 + 20 * i),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2,
                    )

            cv2.imshow("Camera", frame)
            if cv2.waitKey(1) == ord("q"):
                break
    finally:
        cap.release()
        recognizer.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
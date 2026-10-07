import cv2, sys, time, numpy as np
import mediapipe as mp
from collections import deque, Counter
from tensorflow.keras.models import load_model
from utils import extract_hands, normalize_seq

CATEGORY = sys.argv[1] if len(sys.argv) > 1 else "GREETINGS"
SEQ_LEN, WINDOW, PREDICT_EVERY = 30, 45, 5
THRESHOLD, SMOOTH, MIN_HAND_FRAMES = 0.7, 5, 8
RECORD_SECONDS = 5.0

model = load_model(f"models/{CATEGORY}_hands.h5")
labels = np.load(f"models/{CATEGORY}_hands_labels.npy")
model(np.zeros((1, SEQ_LEN, 90), dtype="float32"), training=False)   # warm-up

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

def predict(frames):
    idx = np.linspace(0, len(frames) - 1, SEQ_LEN).astype(int)
    x = normalize_seq(np.array(frames)[idx]).astype("float32")[None]
    return model(x, training=False).numpy()[0]

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

buffer, hand_flags, recent = deque(maxlen=WINDOW), deque(maxlen=WINDOW), deque(maxlen=SMOOTH)
live = recording = False
rec_frames, rec_start = [], 0
text = "SPACE = record a sign | L = live | Q = quit"
frame_count, prev_t, fps = 0, time.time(), 0

with mp_hands.Hands(static_image_mode=False, max_num_hands=2, model_complexity=0,
                    min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        feats = extract_hands(res)
        has_hand = bool(res.multi_hand_landmarks)
        frame_count += 1

        if res.multi_hand_landmarks:
            for lm in res.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS)

        if recording:
            rec_frames.append(feats)
            elapsed = time.time() - rec_start
            text = f"RECORDING... {RECORD_SECONDS - elapsed:.1f}s"
            if elapsed >= RECORD_SECONDS:
                recording = False
                if sum(np.any(f != 0) for f in rec_frames) >= MIN_HAND_FRAMES:
                    p = predict(rec_frames)
                    text = f"{labels[p.argmax()]}  ({p.max():.2f})"
                else:
                    text = "No hands seen, try again"
        elif live:
            buffer.append(feats); hand_flags.append(has_hand)
            if len(buffer) == WINDOW and sum(hand_flags) >= MIN_HAND_FRAMES:
                if frame_count % PREDICT_EVERY == 0:
                    p = predict(list(buffer))
                    recent.append(int(p.argmax()) if p.max() > THRESHOLD else -1)
                    top, cnt = Counter(recent).most_common(1)[0]
                    if cnt >= SMOOTH // 2 + 1:
                        text = f"{labels[top]}  ({p.max():.2f})" if top != -1 else "..."
            elif sum(hand_flags) < MIN_HAND_FRAMES:
                recent.clear(); text = "LIVE: waiting for sign..."

        now = time.time()
        fps = 0.9 * fps + 0.1 * (1 / max(now - prev_t, 1e-6)); prev_t = now
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), (0, 0, 0), -1)
        cv2.putText(frame, text, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2.putText(frame, f"FPS {fps:.0f}  {'LIVE' if live else 'PRESS'}", (10, frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow("ISL hands - " + CATEGORY, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" ") and not recording:
            recording, rec_frames, rec_start, live = True, [], time.time(), False
        elif key == ord("l"):
            live = not live
            buffer.clear(); hand_flags.clear(); recent.clear()
            text = "LIVE: waiting for sign..." if live else "SPACE = record a sign"

cap.release(); cv2.destroyAllWindows()
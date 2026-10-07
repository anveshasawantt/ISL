import cv2, os, sys, numpy as np
import mediapipe as mp
from utils import extract_hands

CATEGORY = sys.argv[1] if len(sys.argv) > 1 else "GREETINGS"
SEQ_LEN = 30
DATA_DIR = os.path.join("dataset", CATEGORY)
OUT_DIR = os.path.join("keypoints_hands", CATEGORY)

mp_hands = mp.solutions.hands
total = 0
with mp_hands.Hands(static_image_mode=False, max_num_hands=2, model_complexity=0,
                    min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
    for sign in sorted(os.listdir(DATA_DIR)):
        sign_path = os.path.join(DATA_DIR, sign)
        if not os.path.isdir(sign_path):
            continue
        os.makedirs(os.path.join(OUT_DIR, sign), exist_ok=True)
        videos = [f for f in os.listdir(sign_path) if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".webm"))]
        saved = 0
        for vid in videos:
            cap = cv2.VideoCapture(os.path.join(sign_path, vid))
            frames = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                frames.append(extract_hands(res))
            cap.release()
            if len(frames) < 5:
                print("   skipped:", vid)
                continue
            idx = np.linspace(0, len(frames) - 1, SEQ_LEN).astype(int)
            np.save(os.path.join(OUT_DIR, sign, os.path.splitext(vid)[0] + ".npy"), np.array(frames)[idx])
            saved += 1
        total += saved
        print(f"[{sign}] {len(videos)} videos, saved {saved}")
print("TOTAL saved:", total)
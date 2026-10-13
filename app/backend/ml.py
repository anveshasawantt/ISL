import os
import sys
import math
import tempfile
import joblib
import numpy as np
import cv2
import mediapipe as mp
import tensorflow as tf

# Import utils directly from root D:\ISL PROJECT\utils.py
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils import extract_hands, normalize_seq
from config import (
    MODEL_PATH,
    LABELS_PATH,
    ALPHABETS_MODEL_PATH,
    NUMBERS_MODEL_PATH,
    WINDOW_SECONDS,
    WINDOW_STRIDE_SECONDS,
    TARGET_FRAMES,
    MIN_VISIBLE_HAND_FRAMES,
    MIRROR_INPUT
)

# Global models cache
_MODEL = None
_LABELS = None
_LABEL_TO_INDEX = {}

_ALPHABETS_MODEL = None
_NUMBERS_MODEL = None

def get_model_and_labels():
    global _MODEL, _LABELS, _LABEL_TO_INDEX
    if _MODEL is None:
        print("[ML] Loading Keras LSTM model from:", MODEL_PATH)
        _MODEL = tf.keras.models.load_model(MODEL_PATH)
        _LABELS = np.load(LABELS_PATH)
        _LABEL_TO_INDEX = {str(lbl): idx for idx, lbl in enumerate(_LABELS)}
        # Warmup model
        dummy = np.zeros((1, TARGET_FRAMES, 90), dtype=np.float32)
        _MODEL.predict(dummy, verbose=0)
        print(f"[ML] LSTM Model warmed up successfully. Total classes: {len(_LABELS)}")
    return _MODEL, _LABELS, _LABEL_TO_INDEX

def get_alphabets_model():
    global _ALPHABETS_MODEL
    if _ALPHABETS_MODEL is None and os.path.exists(ALPHABETS_MODEL_PATH):
        print("[ML] Loading Alphabets model from:", ALPHABETS_MODEL_PATH)
        _ALPHABETS_MODEL = joblib.load(ALPHABETS_MODEL_PATH)
    return _ALPHABETS_MODEL

def get_numbers_model():
    global _NUMBERS_MODEL
    if _NUMBERS_MODEL is None and os.path.exists(NUMBERS_MODEL_PATH):
        print("[ML] Loading Numbers model from:", NUMBERS_MODEL_PATH)
        _NUMBERS_MODEL = joblib.load(NUMBERS_MODEL_PATH)
    return _NUMBERS_MODEL

# ----------------- Angle and Feature extractors for RF Models -----------------

def calculate_angle(p1, p2, p3):
    v1 = np.array([p1.x - p2.x, p1.y - p2.y, p1.z - p2.z])
    v2 = np.array([p3.x - p2.x, p3.y - p2.y, p3.z - p2.z])
    v1_norm = np.linalg.norm(v1)
    v2_norm = np.linalg.norm(v2)
    if v1_norm == 0 or v2_norm == 0:
        return 0.0
    cos_theta = np.dot(v1, v2) / (v1_norm * v2_norm)
    return math.degrees(math.acos(np.clip(cos_theta, -1.0, 1.0)))

def extract_angle_features(hand_landmarks):
    features = []
    wrist = hand_landmarks.landmark[0]
    for lm in hand_landmarks.landmark:
        features.extend([lm.x - wrist.x, lm.y - wrist.y, lm.z - wrist.z])
    lms = hand_landmarks.landmark
    triplets = [
        (0,1,2),(1,2,3),(2,3,4),(0,5,6),(5,6,7),(6,7,8),
        (0,9,10),(9,10,11),(10,11,12),(0,13,14),(13,14,15),(14,15,16),
        (0,17,18),(17,18,19),(18,19,20),(5,0,9),(9,0,13),(13,0,17),(5,0,17)
    ]
    for a, b, c in triplets:
        features.append(calculate_angle(lms[a], lms[b], lms[c]))
    return features

# ----------------- Video Frame Decoder -----------------

def decode_video_frames(video_bytes: bytes, filename: str = "video.mp4") -> tuple[list[np.ndarray], float]:
    ext = os.path.splitext(filename)[1].lower() or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        temp_input = f.name
        f.write(video_bytes)

    frames = []
    fps = 30.0

    try:
        cap = cv2.VideoCapture(temp_input)
        if cap.isOpened():
            detected_fps = cap.get(cv2.CAP_PROP_FPS)
            if detected_fps and detected_fps > 5:
                fps = float(detected_fps)
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
            cap.release()

        # If OpenCV failed or yielded 0 frames, convert with imageio-ffmpeg
        if len(frames) == 0:
            import imageio_ffmpeg
            import subprocess

            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            temp_output = temp_input + "_converted.mp4"
            cmd = [
                ffmpeg_exe, "-y", "-i", temp_input,
                "-c:v", "libx264", "-pix_fmt", "bgr24", temp_output
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            cap = cv2.VideoCapture(temp_output)
            if cap.isOpened():
                detected_fps = cap.get(cv2.CAP_PROP_FPS)
                if detected_fps and detected_fps > 5:
                    fps = float(detected_fps)
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frames.append(frame)
                cap.release()
            if os.path.exists(temp_output):
                os.remove(temp_output)
    finally:
        if os.path.exists(temp_input):
            os.remove(temp_input)

    return frames, fps

# ----------------- Feature Extraction for LSTM -----------------

def process_video_frames(
    frames: list[np.ndarray],
    mirror_input: bool = MIRROR_INPUT
) -> tuple[np.ndarray, np.ndarray, float]:
    if not frames:
        return np.zeros((0, 126)), np.zeros(0, dtype=bool), 0.0

    mp_hands = mp.solutions.hands
    all_features = []
    visible_mask = []

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=0,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as hands:
        for frame in frames:
            if mirror_input:
                frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = hands.process(rgb)
            feats = extract_hands(res)
            all_features.append(feats)
            has_hand = bool(np.any(feats != 0))
            visible_mask.append(has_hand)

    all_features = np.array(all_features, dtype=np.float32)
    visible_mask = np.array(visible_mask, dtype=bool)
    ratio = float(np.mean(visible_mask)) if len(visible_mask) > 0 else 0.0

    return all_features, visible_mask, ratio

# ----------------- Evaluation Pipeline for RF (ALPHABETS / NUMBERS) -----------------

def evaluate_rf_video(
    frames: list[np.ndarray],
    rf_model,
    target_class: str,
    mirror_input: bool = False
):
    mp_hands = mp.solutions.hands
    visible_count = 0
    predictions_probs = []

    classes = list(rf_model.classes_)
    target_idx = None
    target_norm = target_class.strip().upper()
    for idx, c in enumerate(classes):
        if str(c).strip().upper() == target_norm:
            target_idx = idx
            break

    if target_idx is None:
        # Fallback if class not in model classes
        target_idx = 0

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3
    ) as hands:
        for frame in frames:
            if mirror_input:
                frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = hands.process(rgb)
            if res.multi_hand_landmarks:
                visible_count += 1
                if len(res.multi_hand_landmarks) == 2:
                    f1 = extract_angle_features(res.multi_hand_landmarks[0])
                    f2 = extract_angle_features(res.multi_hand_landmarks[1])
                    feats = f1 + f2
                else:
                    f1 = extract_angle_features(res.multi_hand_landmarks[0])
                    feats = f1 + [0.0] * 82
                probs = rf_model.predict_proba(np.array([feats]))[0]
                predictions_probs.append(probs)

    ratio = visible_count / len(frames) if frames else 0.0

    if visible_count < MIN_VISIBLE_HAND_FRAMES or not predictions_probs:
        return {
            "error": "No hands detected, record again",
            "hands_visible_count": visible_count,
            "hands_visible_ratio": ratio,
        }

    # Window probabilities from RF predictions
    window_probs = np.array(predictions_probs)

    return {
        "success": True,
        "window_probabilities": window_probs,
        "hands_visible_ratio": ratio,
        "hands_visible_count": visible_count,
        "labels": np.array(classes),
        "target_index": target_idx,
        "is_rf": True
    }

# ----------------- Main evaluate_video dispatcher -----------------

def evaluate_video(
    video_bytes: bytes,
    filename: str,
    target_category: str,
    target_sign: str,
    mirror_input: bool = MIRROR_INPUT
):
    frames, fps = decode_video_frames(video_bytes, filename)
    if not frames:
        raise ValueError("Could not decode any frames from the submitted video.")

    cat_upper = target_category.strip().upper()

    # Route ALPHABETS to Random Forest
    if cat_upper == "ALPHABETS":
        alph_model = get_alphabets_model()
        if alph_model is not None:
            return evaluate_rf_video(frames, alph_model, target_sign, mirror_input=mirror_input)

    # Route NUMBERS to Random Forest
    if cat_upper == "NUMBERS":
        num_model = get_numbers_model()
        if num_model is not None:
            # Map sign like "0 one" -> "0"
            clean_sign = target_sign.split()[0].upper()
            return evaluate_rf_video(frames, num_model, clean_sign, mirror_input=mirror_input)

    # Standard LSTM Evaluation (GREETINGS, RELATIONS, EMERGENCY, BASIC_NEEDS)
    model, labels, label_to_index = get_model_and_labels()
    features, visible_mask, hands_ratio = process_video_frames(frames, mirror_input=mirror_input)
    visible_count = int(np.sum(visible_mask))

    if visible_count < MIN_VISIBLE_HAND_FRAMES:
        return {
            "error": "No hands detected, record again",
            "hands_visible_count": visible_count,
            "hands_visible_ratio": hands_ratio,
        }

    first_visible = int(np.where(visible_mask)[0][0])
    last_visible = int(np.where(visible_mask)[0][-1])
    span_features = features[first_visible : last_visible + 1]

    window_frame_len = max(int(round(WINDOW_SECONDS * fps)), TARGET_FRAMES)
    stride_frames = max(1, int(round(WINDOW_STRIDE_SECONDS * fps)))

    windows_seq = []
    if len(span_features) <= window_frame_len:
        idx = np.linspace(0, len(span_features) - 1, TARGET_FRAMES).astype(int)
        windows_seq.append(normalize_seq(span_features[idx]))
    else:
        start = 0
        while start + window_frame_len <= len(span_features):
            w = span_features[start : start + window_frame_len]
            idx = np.linspace(0, len(w) - 1, TARGET_FRAMES).astype(int)
            windows_seq.append(normalize_seq(w[idx]))
            start += stride_frames

        if start - stride_frames + window_frame_len < len(span_features):
            w = span_features[-window_frame_len:]
            idx = np.linspace(0, len(w) - 1, TARGET_FRAMES).astype(int)
            windows_seq.append(normalize_seq(w[idx]))

    batch_x = np.array(windows_seq, dtype=np.float32)
    all_window_preds = model.predict(batch_x, verbose=0)

    return {
        "success": True,
        "window_probabilities": all_window_preds,
        "hands_visible_ratio": hands_ratio,
        "hands_visible_count": visible_count,
        "labels": labels,
        "label_to_index": label_to_index,
        "is_rf": False
    }

import cv2
import mediapipe as mp
import numpy as np
import math
import joblib

MODEL_PATH = r"D:\ISL PROJECT\isl_video_model.pkl"

# ── setup ─────────────────────────────────────────────────────────────────────

model = joblib.load(MODEL_PATH)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=True,
    max_num_hands=2,
    min_detection_confidence=0.3,
    min_tracking_confidence=0.3
)

CONFIDENCE_THRESHOLD = 0.30

# ── helpers (identical to day4) ───────────────────────────────────────────────

def calculate_angle(p1, p2, p3):
    v1 = np.array([p1.x - p2.x, p1.y - p2.y, p1.z - p2.z])
    v2 = np.array([p3.x - p2.x, p3.y - p2.y, p3.z - p2.z])
    v1_norm = np.linalg.norm(v1)
    v2_norm = np.linalg.norm(v2)
    if v1_norm == 0 or v2_norm == 0:
        return 0.0
    cos_theta = np.dot(v1, v2) / (v1_norm * v2_norm)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    return math.degrees(math.acos(cos_theta))


def extract_features(hand_landmarks):
    features = []
    wrist = hand_landmarks.landmark[0]
    for lm in hand_landmarks.landmark:
        features.extend([lm.x - wrist.x,
                         lm.y - wrist.y,
                         lm.z - wrist.z])
    lms = hand_landmarks.landmark
    triplets = [
        (0,1,2),(1,2,3),(2,3,4),
        (0,5,6),(5,6,7),(6,7,8),
        (0,9,10),(9,10,11),(10,11,12),
        (0,13,14),(13,14,15),(14,15,16),
        (0,17,18),(17,18,19),(18,19,20),
        (5,0,9),(9,0,13),(13,0,17),(5,0,17)
    ]
    for a, b, c in triplets:
        features.append(calculate_angle(lms[a], lms[b], lms[c]))
    return features


# ── main predict function ─────────────────────────────────────────────────────

def predict_frame(frame_bgr, target_letter=None):
    """
    Takes a BGR webcam frame.
    Returns a result dict.
    
    target_letter: str or None
      - None       → free mode, just return prediction
      - "A"        → practice/quiz mode, compare and give feedback
    """
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    # No hand detected
    if not results.multi_hand_landmarks:
        return {
            "hand_detected": False,
            "predicted":     "",
            "confidence":    0.0,
            "correct":       False,
            "feedback":      "No hand detected — position your hand in frame."
        }

    # Extract features
    if len(results.multi_hand_landmarks) == 2:
        f1 = extract_features(results.multi_hand_landmarks[0])
        f2 = extract_features(results.multi_hand_landmarks[1])
        features = f1 + f2
    else:
        f1 = extract_features(results.multi_hand_landmarks[0])
        features = f1 + [0.0] * 82

    # Predict
    probs      = model.predict_proba(np.array([features]))[0]
    predicted  = model.classes_[np.argmax(probs)]
    confidence = float(np.max(probs))

    # Below threshold → treat as no prediction
    if confidence < CONFIDENCE_THRESHOLD:
        predicted = ""

    # ── free mode ─────────────────────────────────────────────────────────────
    if target_letter is None:
        return {
            "hand_detected": True,
            "predicted":     predicted,
            "confidence":    round(confidence, 2),
            "correct":       None,
            "feedback":      ""
        }

    # ── practice / quiz mode ──────────────────────────────────────────────────
    target = target_letter.upper()

    if predicted == target and confidence >= 0.50:
        correct  = True
        feedback = f"Correct! ✅ That's {target}!"

    elif predicted == target and confidence < 0.50:
        correct  = False
        feedback = f"Almost! Hold the {target} sign more steadily."

    elif predicted != "" and predicted != target:
        correct  = False
        feedback = f"Not quite — looks like {predicted}. Try adjusting your hand."

    else:
        correct  = False
        feedback = f"Keep trying! Make sure your hand is visible."

    return {
        "hand_detected": True,
        "predicted":     predicted,
        "confidence":    round(confidence, 2),
        "correct":       correct,
        "feedback":      feedback,
        "target":        target
    }


def predict_batch(frames_bgr, target_letter=None):
    """
    Takes a list of BGR frames.
    Returns majority vote result — more stable for quiz mode.
    """
    predictions = []
    confidences = []

    for frame in frames_bgr:
        result = predict_frame(frame, target_letter=None)
        if result["hand_detected"] and result["predicted"] != "":
            predictions.append(result["predicted"])
            confidences.append(result["confidence"])

    if not predictions:
        return {
            "hand_detected": False,
            "predicted":     "",
            "confidence":    0.0,
            "correct":       False,
            "feedback":      "No hand detected in any frame."
        }

    # Majority vote
    from collections import Counter
    most_common, count = Counter(predictions).most_common(1)[0]
    avg_confidence = round(sum(confidences) / len(confidences), 2)

    # Build final result using single-frame logic for feedback
    dummy_result = {
        "hand_detected": True,
        "predicted":     most_common,
        "confidence":    avg_confidence
    }

    if target_letter is None:
        dummy_result["correct"]  = None
        dummy_result["feedback"] = ""
        dummy_result["votes"]    = dict(Counter(predictions))
        return dummy_result

    target = target_letter.upper()

    if most_common == target and avg_confidence >= 0.50:
        correct  = True
        feedback = f"Correct! ✅ That's {target}!"
    elif most_common == target:
        correct  = False
        feedback = f"Almost! Hold the {target} sign more steadily."
    else:
        correct  = False
        feedback = f"Not quite — looks like {most_common}. Try adjusting."

    dummy_result["correct"]  = correct
    dummy_result["feedback"] = feedback
    dummy_result["target"]   = target
    dummy_result["votes"]    = dict(Counter(predictions))
    return dummy_result
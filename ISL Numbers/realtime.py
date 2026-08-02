import cv2
import mediapipe as mp
import numpy as np
import math
import joblib
import os
import time

MODEL_PATH = r"C:\ISL PROJECT\data\isl_numbers_model.pkl"

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

DIGIT_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"
}

class NumberSequenceBuilder:
    """
    Builds a compound number (e.g. 1 -> LAKH => 100000) from a
    sequence of held signs: digits 0-9, HUNDRED, THOUSAND, LAKH, CRORE.
    Supports undoing the last committed sign or clearing everything.
    """
    PLACE_VALUES = {
        "HUNDRED": 100,
        "THOUSAND": 1000,
        "LAKH": 100000,
        "CRORE": 10000000,
    }

    def __init__(self, confidence_threshold=0.45, hold_duration=1.0):
        self.confidence_threshold = confidence_threshold
        self.hold_duration = hold_duration

        self.tracking_sign = None
        self.tracking_start_time = 0
        self.last_committed_sign = None

        self.sequence = []
        self.hand_was_visible = False

    def process_frame(self, prediction, confidence, hand_detected):
        current_time = time.time()

        if not hand_detected or confidence < self.confidence_threshold:
            if self.hand_was_visible:
                self.hand_was_visible = False
                self.tracking_sign = None
            return

        self.hand_was_visible = True

        if prediction != self.tracking_sign:
            self.tracking_sign = prediction
            self.tracking_start_time = current_time
        else:
            held_for = current_time - self.tracking_start_time
            if held_for >= self.hold_duration and prediction != self.last_committed_sign:
                self._commit(prediction)
                self.tracking_start_time = current_time

    def _commit(self, sign):
        self.sequence.append(sign)
        self.last_committed_sign = sign

    def delete_last(self):
        """Removes the most recently committed sign (undo a wrong detection)."""
        if self.sequence:
            self.sequence.pop()
            self.last_committed_sign = self.sequence[-1] if self.sequence else None
            self.tracking_sign = None  # force re-hold before next commit

    def get_progress(self):
        if self.tracking_sign is None:
            return 0
        held_for = time.time() - self.tracking_start_time
        return min(100, int((held_for / self.hold_duration) * 100))

    def compute_value(self):
        if not self.sequence:
            return None
        total = 0
        current_digit = 0
        for token in self.sequence:
            if token.isdigit():
                current_digit = current_digit * 10 + int(token)
            elif token in self.PLACE_VALUES:
                multiplier = self.PLACE_VALUES[token]
                total += (current_digit if current_digit else 1) * multiplier
                current_digit = 0
        total += current_digit
        return total

    def to_words(self):
        """Human-readable form, e.g. ['1','LAKH'] -> 'one lakh'."""
        words = []
        for token in self.sequence:
            words.append(DIGIT_WORDS[token] if token.isdigit() else token.lower())
        return " ".join(words)

    def reset(self):
        self.sequence = []
        self.tracking_sign = None
        self.last_committed_sign = None


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
        features.extend([lm.x - wrist.x, lm.y - wrist.y, lm.z - wrist.z])

    lms = hand_landmarks.landmark
    angle_triplets = [
        (0, 1, 2), (1, 2, 3), (2, 3, 4),
        (0, 5, 6), (5, 6, 7), (6, 7, 8),
        (0, 9, 10), (9, 10, 11), (10, 11, 12),
        (0, 13, 14), (13, 14, 15), (14, 15, 16),
        (0, 17, 18), (17, 18, 19), (18, 19, 20),
        (5, 0, 9), (9, 0, 13), (13, 0, 17), (5, 0, 17)
    ]
    for p1_idx, p2_idx, p3_idx in angle_triplets:
        features.append(calculate_angle(lms[p1_idx], lms[p2_idx], lms[p3_idx]))
    return features


def run_realtime():
    if not os.path.exists(MODEL_PATH):
        print(f"Model file not found at {MODEL_PATH}. Run train.py first.")
        return

    print("Loading model...")
    model = joblib.load(MODEL_PATH)

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3
    )

    cap = cv2.VideoCapture(0)
    builder = NumberSequenceBuilder(confidence_threshold=0.45, hold_duration=1.0)

    print("Sign any number. Controls: Q=Quit | C=Clear all | Backspace=Undo last sign")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # 1. Extract landmarks + predict on the ORIGINAL (unflipped) frame
        #    This matches extract.py, which never flips training videos.
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        hand_detected = False
        top_pred = ""
        confidence = 0.0

        if results.multi_hand_landmarks:
            hand_detected = True
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            if len(results.multi_hand_landmarks) == 2:
                f1 = extract_features(results.multi_hand_landmarks[0])
                f2 = extract_features(results.multi_hand_landmarks[1])
                features = f1 + f2
            else:
                f1 = extract_features(results.multi_hand_landmarks[0])
                features = f1 + [0.0] * 82

            probs = model.predict_proba(np.array([features]))[0]
            top_pred = model.classes_[np.argmax(probs)]
            confidence = np.max(probs)

        builder.process_frame(top_pred, confidence, hand_detected)

        # 2. Flip the ANNOTATED frame now, purely for natural mirror-view display.
        #    Landmarks were already drawn in step 1, so they flip along with the image.
        frame = cv2.flip(frame, 1)

        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 190), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        live_pred = top_pred if confidence >= 0.45 and hand_detected else ""
        cv2.putText(frame, f"Detected: {live_pred} ({int(confidence * 100)}%)", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 0), 2)

        cv2.putText(frame, f"Sequence: {' '.join(builder.sequence)}", (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        computed = builder.compute_value()
        value_text = f"{computed:,}" if computed is not None else "-"
        cv2.putText(frame, f"Number: {value_text}", (20, 105),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

        words = builder.to_words()
        cv2.putText(frame, f"Words: {words}", (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

        progress = builder.get_progress()
        cv2.putText(frame, f"Hold progress: {progress}%", (20, 170),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

        cv2.rectangle(frame, (0, h - 35), (w, h), (0, 0, 0), -1)
        cv2.putText(frame, "Q=Quit | C=Clear | Backspace=Undo last",
                    (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        cv2.imshow('ISL Number Recognition (Free Mode)', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            builder.reset()
        elif key == 8:  # Backspace
            builder.delete_last()

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_realtime()
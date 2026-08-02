import os
import cv2
import mediapipe as mp

print(mp.__file__)
print(mp.solutions)

import csv
import numpy as np
import math

DATASET_PATH = r"C:\ISL PROJECT\Numbers"
CSV_PATH = r"C:\ISL PROJECT\data\isl_numbers_angles_2hands.csv"

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.3,
    min_tracking_confidence=0.3
)

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

def process_dataset():
    if not os.path.exists(DATASET_PATH):
        print(f"Dataset path {DATASET_PATH} does not exist. Please update DATASET_PATH.")
        return

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)  # auto-creates "data" folder

    with open(CSV_PATH, 'w', newline='') as f:
        writer = csv.writer(f)
        header = ['label']
        for hand in range(2):
            for i in range(21):
                header.extend([f'h{hand}_lm_{i}_x', f'h{hand}_lm_{i}_y', f'h{hand}_lm_{i}_z'])
            for i in range(19):
                header.append(f'h{hand}_angle_{i}')
        writer.writerow(header)

        files = [f for f in os.listdir(DATASET_PATH) if f.endswith(('.mp4', '.avi', '.mov', '.mkv'))]
        for file in files:
            label = file.split(' ')[0].upper()   # full first word
            video_path = os.path.join(DATASET_PATH, file)
            cap = cv2.VideoCapture(video_path)

            frame_count = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb_frame)

                if results.multi_hand_landmarks:
                    if len(results.multi_hand_landmarks) == 2:
                        f1 = extract_features(results.multi_hand_landmarks[0])
                        f2 = extract_features(results.multi_hand_landmarks[1])
                        features = f1 + f2
                    else:
                        f1 = extract_features(results.multi_hand_landmarks[0])
                        features = f1 + [0.0] * 82

                    writer.writerow([label] + features)
                    frame_count += 1

            cap.release()
            print(f"Processed {file}: {frame_count} frames extracted for label {label}.")

if __name__ == "__main__":
    process_dataset()
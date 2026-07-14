import cv2
import mediapipe as mp
import numpy as np
import math
import joblib
import os
from collections import deque, Counter

MODEL_PATH = r"D:\ISL PROJECT\isl_video_model.pkl"

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

def calculate_angle(p1, p2, p3):
    # Calculate angle between three points (p2 is the vertex)
    # Using vectors p2->p1 and p2->p3
    v1 = np.array([p1.x - p2.x, p1.y - p2.y, p1.z - p2.z])
    v2 = np.array([p3.x - p2.x, p3.y - p2.y, p3.z - p2.z])
    
    v1_norm = np.linalg.norm(v1)
    v2_norm = np.linalg.norm(v2)
    
    if v1_norm == 0 or v2_norm == 0:
        return 0.0
        
    dot_product = np.dot(v1, v2)
    cos_theta = dot_product / (v1_norm * v2_norm)
    # Clip cos_theta to [-1, 1] to avoid math domain errors due to floating point inaccuracies
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    
    angle = math.degrees(math.acos(cos_theta))
    return angle

def extract_features(hand_landmarks):
    features = []
    
    # 1. Normalized keypoints (63 features: 21 landmarks * 3 coordinates)
    wrist = hand_landmarks.landmark[0]
    for lm in hand_landmarks.landmark:
        features.extend([
            lm.x - wrist.x,
            lm.y - wrist.y,
            lm.z - wrist.z
        ])
        
    # 2. Angles (19 features)
    lms = hand_landmarks.landmark
    angle_triplets = [
        # Thumb
        (0, 1, 2), (1, 2, 3), (2, 3, 4),
        # Index
        (0, 5, 6), (5, 6, 7), (6, 7, 8),
        # Middle
        (0, 9, 10), (9, 10, 11), (10, 11, 12),
        # Ring
        (0, 13, 14), (13, 14, 15), (14, 15, 16),
        # Pinky
        (0, 17, 18), (17, 18, 19), (18, 19, 20),
        # Knuckle spread
        (5, 0, 9), (9, 0, 13), (13, 0, 17), (5, 0, 17)
    ]
    
    for p1_idx, p2_idx, p3_idx in angle_triplets:
        angle = calculate_angle(lms[p1_idx], lms[p2_idx], lms[p3_idx])
        features.append(angle)
        
    return features

def run_realtime():
    if not os.path.exists(MODEL_PATH):
        print(f"Model file not found at {MODEL_PATH}. Run day3_train.py first.")
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
    
    print("Starting webcam... Press 'q' to quit.")
    
    prediction_buffer = deque(maxlen=15)
    stable_letter = ""
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Flip frame horizontally for natural viewing
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        results = hands.process(rgb_frame)
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                
            if len(results.multi_hand_landmarks) == 2:
                features_hand1 = extract_features(results.multi_hand_landmarks[0])
                features_hand2 = extract_features(results.multi_hand_landmarks[1])
                features = features_hand1 + features_hand2
            else:
                features_hand1 = extract_features(results.multi_hand_landmarks[0])
                features = features_hand1 + [0.0] * 82
            
            # Predict
            probs = model.predict_proba(np.array([features]))[0]
            top_pred = model.classes_[np.argmax(probs)]
            confidence = np.max(probs)
            print(f"Pred: {top_pred} | Conf: {int(confidence * 100)}%")
            
            prediction_buffer.append(top_pred)
            if len(prediction_buffer) == 15:
                most_common, count = Counter(prediction_buffer).most_common(1)[0]
                if count >= 10:
                    stable_letter = most_common
            
            # Display prediction
            cv2.putText(frame, f"Letter: {stable_letter} ({int(confidence * 100)}%)", (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
                            
        cv2.imshow('ISL Real-time Recognition', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_realtime()

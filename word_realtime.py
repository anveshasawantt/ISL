import cv2
import mediapipe as mp
import numpy as np
import math
import joblib
import keras
from collections import deque, Counter
import os

model_path   = r"D:\ISL PROJECT\words_lstm_model.keras"
encoder_path = r"D:\ISL PROJECT\words_label_encoder.pkl"

def calculate_angle(p1, p2, p3):
    v1 = np.array([p1.x - p2.x, p1.y - p2.y, p1.z - p2.z])
    v2 = np.array([p3.x - p2.x, p3.y - p2.y, p3.z - p2.z])
    v1_norm = np.linalg.norm(v1)
    v2_norm = np.linalg.norm(v2)
    if v1_norm == 0 or v2_norm == 0:
        return 0.0
    dot_product = np.dot(v1, v2)
    cos_theta = dot_product / (v1_norm * v2_norm)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    angle = math.degrees(math.acos(cos_theta))
    return angle

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
        angle = calculate_angle(lms[p1_idx], lms[p2_idx], lms[p3_idx])
        features.append(angle)
    return features

def main():
    if not os.path.exists(model_path):
        print(f"Model not found at {model_path}. Train the model first.")
        return
        
    print("Loading model and encoder...")
    model = keras.models.load_model(model_path, compile=False)
    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    le = joblib.load(encoder_path)
    
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3
    )
    
    frame_buffer = deque(maxlen=30)
    prediction_buffer = deque(maxlen=20)
    stable_word = ""
    
    cap = cv2.VideoCapture(0)
    print("Starting webcam... Press SPACE to clear, Q to quit.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
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
                
            frame_buffer.append(features)
        
        predicted_word = ""
        confidence = 0.0
        
        if len(frame_buffer) == 30:
            sequence = np.array(frame_buffer)
            pred = model.predict(sequence[np.newaxis, ...], verbose=0)
            predicted_word = le.inverse_transform([np.argmax(pred)])[0]
            confidence = np.max(pred)
            
            prediction_buffer.append(predicted_word)
            
            print(f"Pred: {predicted_word} | Conf: {confidence:.2f}")
            
            if len(prediction_buffer) > 0:
                most_common = Counter(prediction_buffer).most_common(1)[0]
                if most_common[1] >= 14:
                    stable_word = most_common[0]
                    
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 100), (0, 0, 0), -1)
        
        cv2.putText(frame, f"Word: {stable_word}", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 255, 0), 3)
                    
        cv2.putText(frame, f"Live: {predicted_word} ({int(confidence*100)}%)", (20, 90), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    
        cv2.putText(frame, "Press Q to quit | SPACE to clear", (20, h - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
                    
        cv2.imshow("ISL Word Recognition", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == 32: # SPACE
            stable_word = ""
            frame_buffer.clear()
            prediction_buffer.clear()
            print("Buffers cleared.")
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

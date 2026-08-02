import os
import cv2
import math
import numpy as np
import mediapipe as mp

dataset_path = r"D:\ISL PROJECT\words"
X_path       = r"D:\ISL PROJECT\words_X.npy"
y_path       = r"D:\ISL PROJECT\words_y.npy"
SEQUENCE_LENGTH = 30

mp_hands = mp.solutions.hands

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
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.3,
        min_tracking_confidence=0.3
    )
    
    valid_extensions = ('.mp4', '.avi', '.mov', '.mkv')
    
    X = []
    y = []
    
    if not os.path.exists(dataset_path):
        print(f"Dataset path {dataset_path} does not exist.")
        return

    word_folders = [f for f in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, f))]
    word_folders.sort()
    
    total_saved = 0
    total_skipped = 0
    
    word_counts = {}
    
    for word in word_folders:
        word_path = os.path.join(dataset_path, word)
        videos = [f for f in os.listdir(word_path) if f.lower().endswith(valid_extensions)]
        word_saved_count = 0
        
        for video_file in videos:
            video_path = os.path.join(word_path, video_file)
            cap = cv2.VideoCapture(video_path)
            
            video_frames = []
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                    
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb_frame)
                
                if results.multi_hand_landmarks:
                    if len(results.multi_hand_landmarks) == 2:
                        features_hand1 = extract_features(results.multi_hand_landmarks[0])
                        features_hand2 = extract_features(results.multi_hand_landmarks[1])
                        features = features_hand1 + features_hand2
                    else:
                        features_hand1 = extract_features(results.multi_hand_landmarks[0])
                        features = features_hand1 + [0.0] * 82
                    video_frames.append(features)
                    
            cap.release()
            
            if len(video_frames) < SEQUENCE_LENGTH:
                print(f"Warning: Skipping {video_path}. Valid frames ({len(video_frames)}) < {SEQUENCE_LENGTH}")
                total_skipped += 1
            else:
                indices = np.linspace(0, len(video_frames) - 1, SEQUENCE_LENGTH).astype(int)
                sampled_frames = [video_frames[i] for i in indices]
                X.append(sampled_frames)
                y.append(word)
                word_saved_count += 1
                total_saved += 1
                
        word_counts[word] = word_saved_count
        
    hands.close()
    
    if len(X) == 0:
        print("No valid sequences extracted. Check dataset.")
        return
        
    X = np.array(X)
    y = np.array(y)
    
    np.save(X_path, X)
    np.save(y_path, y)
    
    print("-" * 30)
    for word, count in word_counts.items():
        print(f"Word: {word:<15} Sequences: {count}")
    print("-" * 30)
    print(f"Total sequences saved: {total_saved}")
    print(f"Total sequences skipped: {total_skipped}")
    print(f"X shape: {X.shape}")
    print(f"y shape: {y.shape}")

if __name__ == "__main__":
    main()

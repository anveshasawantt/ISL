import os
import cv2

# Update this path to your actual dataset directory
DATASET_PATH = r"D:\ISL PROJECT\Alphabets"

def check_dataset(dataset_path):
    if not os.path.exists(dataset_path):
        print(f"Dataset path {dataset_path} does not exist. Please update DATASET_PATH.")
        return

    files = [f for f in os.listdir(dataset_path) if f.endswith(('.mp4', '.avi', '.mov', '.mkv'))]
    
    stats = {}
    total_videos = 0
    total_frames = 0

    for file in files:
        label = file.split(' ')[0][0].upper()
        
        video_path = os.path.join(dataset_path, file)
        cap = cv2.VideoCapture(video_path)
        frames = 0
        if cap.isOpened():
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            
        if label not in stats:
            stats[label] = {'videos': 0, 'frames': 0}
            
        stats[label]['videos'] += 1
        stats[label]['frames'] += frames
        total_videos += 1
        total_frames += frames

    print(f"{'Letter':<10} | {'Videos':<10} | {'Total Frames':<15}")
    print("-" * 40)
    
    for label in sorted(stats.keys()):
        print(f"{label:<10} | {stats[label]['videos']:<10} | {stats[label]['frames']:<15}")

    print("-" * 40)
    print(f"{'Total':<10} | {total_videos:<10} | {total_frames:<15}")

if __name__ == "__main__":
    check_dataset(DATASET_PATH)

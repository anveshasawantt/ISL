import os
import cv2

dataset_path = r"D:\ISL PROJECT\words"

def main():
    if not os.path.exists(dataset_path):
        print(f"Dataset path does not exist: {dataset_path}")
        return

    word_folders = [f for f in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, f))]
    word_folders.sort()
    
    total_words = len(word_folders)
    total_videos_all = 0
    total_frames_all = 0
    
    print(f"{'Word':<15} | {'Videos':<8} | {'Total Frames':<12}")
    print("-" * 45)
    
    valid_extensions = ('.mp4', '.avi', '.mov', '.mkv')
    
    for word in word_folders:
        word_path = os.path.join(dataset_path, word)
        videos = [f for f in os.listdir(word_path) if f.lower().endswith(valid_extensions)]
        
        word_videos = len(videos)
        word_frames = 0
        
        for video_file in videos:
            video_path = os.path.join(word_path, video_file)
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                word_frames += frames
            cap.release()
            
        print(f"{word:<15} | {word_videos:<8} | {word_frames:<12}")
        
        total_videos_all += word_videos
        total_frames_all += word_frames
        
    print("-" * 45)
    print(f"Total Words: {total_words}")
    print(f"Total Videos: {total_videos_all}")
    print(f"Total Frames: {total_frames_all}")
    
    if total_words > 0:
        print(f"Average Frames per Word: {total_frames_all / total_words:.2f}")

if __name__ == '__main__':
    main()

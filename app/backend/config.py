import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # D:\ISL PROJECT
APP_DIR = BASE_DIR / "app"
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_DIR = APP_DIR / "frontend"

MODEL_PATH = str(BASE_DIR / "models" / "all_hands.h5")
LABELS_PATH = str(BASE_DIR / "models" / "all_hands_labels.npy")
ALPHABETS_MODEL_PATH = str(BASE_DIR / "isl_video_model.pkl")
NUMBERS_MODEL_PATH = str(BASE_DIR / "ISL Numbers" / "data" / "isl_numbers_model.pkl")
TUTORIAL_DIR = str(BASE_DIR / "tutorial")
DATASET_DIR = str(BASE_DIR / "dataset")
DATABASE_URL = f"sqlite:///{str(BACKEND_DIR / 'isl_app.db')}"

# Category configuration
# Skip names that do not exist in the tutorial folder (except coming-soon categories),
# and append any other discovered folders before SENTENCES.
CATEGORY_ORDER = ["ALPHABETS", "NUMBERS", "GREETINGS", "RELATIONS", "EMERGENCY", "SENTENCES"]
COMING_SOON_CATEGORIES = ["SENTENCES"]

# Sequential unlock configuration
ENFORCE_CATEGORY_LOCKS = False  # Set to True to enable sequential lock logic
QUIZ_GATES_NEXT_CATEGORY = True  # If True, both all signs passed and quiz passed are required

# Temporary Quiz Unlock Override
# Unlock everything except BASIC_NEEDS (and coming soon SENTENCES)
QUIZ_TEMPORARY_ALL_UNLOCKED = True
QUIZ_ALWAYS_LOCKED_CATEGORIES = ["BASIC_NEEDS", "SENTENCES"]

# Model & Evaluation Configuration
WINDOW_SECONDS = 5.37  # Measured median duration of dataset videos
WINDOW_STRIDE_SECONDS = 0.25
TARGET_FRAMES = 30
MIN_VISIBLE_HAND_FRAMES = 10
MIRROR_INPUT = False  # Flips frames horizontally before extraction if True

PASS_THRESHOLD = 70
QUIZ_PASS_THRESHOLD = 70
QUIZ_MAX_QUESTIONS = None  # None means all signs

# Feedback Bands
FEEDBACK_BANDS = [
    {"min": 0, "max": 49, "text": "PLEASE TRY AGAIN", "band": "try_again", "color": "#FF3B30"},
    {"min": 50, "max": 69, "text": "NEED MORE PRACTICE", "band": "practice", "color": "#FFE500"},
    {"min": 70, "max": 89, "text": "YOU ARE GETTING GOOD", "band": "good", "color": "#3D5AFE"},
    {"min": 90, "max": 100, "text": "JOB WELL DONE", "band": "excellent", "color": "#00C853"},
]

# Auth JWT Config
JWT_SECRET_KEY = "isl-super-secret-jwt-key-for-local-authentication"
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

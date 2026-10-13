# ISL (Indian Sign Language) Full-Stack Learning App

A full-stack, production-grade Indian Sign Language learning and real-time evaluation platform. The backend runs MediaPipe Hands and a TensorFlow Keras LSTM neural network to score user sign performances with zero mock data. The frontend is built with React, Vite, TypeScript, and a bold Neo-Brutalist design aesthetic.

---

## 1. Project Overview & Architecture

- **Backend**: Python FastAPI with SQLite (`app/backend/isl_app.db`), SQLAlchemy ORM, PyJWT authentication, bcrypt password hashing, and real-time video evaluation using TensorFlow and MediaPipe.
- **Machine Learning Integration**: Imports `utils.py` directly from `D:\ISL PROJECT\utils.py` (`extract_hands` and `normalize_seq`). Evaluates user recordings through sliding windows resampled to 30 frames with `np.linspace`.
- **Frontend**: React + Vite + TypeScript with Tailwind CSS in `app/frontend`. Full-bleed edge-to-edge layout, 3.5px solid black borders, hard zero-blur offset shadows (`6px 6px 0 #000`), saturated palette (`#FFE500`, `#FF4D8D`, `#3D5AFE`, `#00C853`, `#FF3B30`), and zero emojis.
- **Tutorial & Streaming**: HTTP Range request video streaming (`GET /api/tutorial/{category}/{sign}`) with seeking support and playback speed controls (0.25x - 1.5x).

---

## 2. Setup & Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.11)
- Node.js 18+ and npm
- Webcam device connected for practice and quiz modes

### Installation Steps

1. **Install Backend Dependencies**:
   ```bash
   cd "D:\ISL PROJECT"
   pip install -r requirements.txt
   ```

2. **Install Frontend Dependencies**:
   ```bash
   cd "D:\ISL PROJECT\app\frontend"
   npm install
   ```

---

## 3. How to Run

### Option A: One-Command Startup (Windows)
Double-click or run:
```cmd
run_all.bat
```
This launches both the FastAPI backend (port 8000) and the Vite frontend (port 5173 with proxy) in separate console windows.

### Option B: Manual Startup

1. **Start Backend**:
   ```bash
   cd "D:\ISL PROJECT\app\backend"
   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Start Frontend**:
   ```bash
   cd "D:\ISL PROJECT\app\frontend"
   npm run dev
   ```

3. Open your browser at:
   `http://localhost:5173`

---

## 4. Configuration Options (`app/backend/config.py`)

All core rules and hyperparameters are centralized in `app/backend/config.py`:

| Setting | Default Value | Description |
|---|---|---|
| `CATEGORY_ORDER` | `["ALPHABETS", "NUMBERS", "GREETINGS", "RELATIONS", "EMERGENCY", "SENTENCES"]` | Ordering of categories. Discovered folders are appended before SENTENCES. |
| `COMING_SOON_CATEGORIES` | `["SENTENCES"]` | Displayed as locked cards with a padlock icon, never clickable, excluded from overall progress. |
| `ENFORCE_CATEGORY_LOCKS` | `False` | When `False`, all active categories are open. When `True`, category N+1 unlocks only after category N is COMPLETED. |
| `QUIZ_GATES_NEXT_CATEGORY` | `True` | When `True`, category completion requires both all signs passed (score >= 70) AND quiz passed (score >= 70). When `False`, passing all signs completes the category. |
| `WINDOW_SECONDS` | `5.37` | Sliding window length in seconds. Derived from the median duration of 501 dataset videos. |
| `WINDOW_STRIDE_SECONDS` | `0.25` | Stride step when sliding the analysis window over visible-hand spans. |
| `MIRROR_INPUT` | `False` | When `True`, flips input video frames horizontally before extraction. |
| `QUIZ_MAX_QUESTIONS` | `None` | Max questions per quiz attempt (`None` tests all signs in random order). |
| `PASS_THRESHOLD` | `70` | Passing score threshold for practice and quiz questions. |

---

## 5. Assumptions

1. **Tutorial Directory Structure**: The tutorial videos reside under `tutorial/LESSONS/<CATEGORY>/` and `tutorial/<CATEGORY>/`. Category folder names ending with ` ok` (e.g., `PEOPLE AND RELATIONS ok`, `BASIC NEEDS ok`) are automatically normalized to their canonical names (`RELATIONS`, `BASIC_NEEDS`, etc.).
2. **Signs without Trained Models**: Signs present in the tutorial directory without corresponding model labels (e.g. `ALPHABETS` and `NUMBERS`) show their full tutorial videos, while their practice button clearly displays the message: *"No trained model for this sign yet"*.
3. **Webcam Browser Compatibility**: MediaRecorder records video in WebM format. When received on the backend, OpenCV decodes the video. If OpenCV fails to read the WebM container, `imageio-ffmpeg` automatically converts the video to MP4/BGR24 before running MediaPipe.
4. **Timezone Handling**: The client browser sends its IANA timezone (e.g. `Asia/Kolkata` or `America/New_York`) via the `X-Timezone` header so that practice and quiz attempts correctly group into calendar days for streak calculation.
5. **Root Directory Integrity**: No existing root files were modified or deleted. Backend and frontend reside entirely in `app/backend` and `app/frontend`.

---

## 6. Verification and Quality Checks

Run the automated backend test suite:
```bash
python app/backend/tests/test_evaluate.py
```
This tests:
1. Two real videos from `dataset/` (`GREETINGS/hello` and `EMERGENCY/fire`) evaluated against their correct targets (scoring 98% and 97%).
2. The `hello` video evaluated against an incorrect target (`EMERGENCY/fire`), scoring 0%.
3. Default lock behavior (`SENTENCES` returns 403, other categories accessible).
4. Quiz gating (quiz returns 403 until all category signs are passed).
5. Sequential lock enforcement (`ENFORCE_CATEGORY_LOCKS = True` locks later categories with clear reason, restored to `False`).

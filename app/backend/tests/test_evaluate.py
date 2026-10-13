import os
import sys
import glob
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from main import app
from database import SessionLocal, init_db
from models import User, Attempt, QuizAttempt

client = TestClient(app)

def test_evaluate_with_real_dataset_videos():
    """
    Take 2 real videos from dataset/ for two different signs,
    send each to evaluate logic with the correct target, and print the scores.
    Also send one video with the wrong target and confirm the score is clearly lower.
    """
    print("\n--- RUNNING TEST: test_evaluate_with_real_dataset_videos ---")
    
    # Register/login test user
    reg_res = client.post("/api/auth/register", json={"username": "test_eval_user", "password": "password123"})
    if reg_res.status_code == 200:
        token = reg_res.json()["access_token"]
    else:
        login_res = client.post("/api/auth/login", json={"username": "test_eval_user", "password": "password123"})
        token = login_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Video 1: GREETINGS/hello
    hello_vids = glob.glob(os.path.join(config.DATASET_DIR, "GREETINGS", "hello", "*.mp4"))
    assert len(hello_vids) > 0, "No hello videos found in dataset/GREETINGS/hello"
    vid1_path = hello_vids[0]

    # Video 2: EMERGENCY/fire
    fire_vids = glob.glob(os.path.join(config.DATASET_DIR, "EMERGENCY", "fire", "*.mp4"))
    assert len(fire_vids) > 0, "No fire videos found in dataset/EMERGENCY/fire"
    vid2_path = fire_vids[0]

    # 1. Evaluate Video 1 with correct target ('GREETINGS', 'hello')
    with open(vid1_path, "rb") as f:
        vid1_bytes = f.read()
    
    res1 = client.post(
        "/api/evaluate",
        headers=headers,
        data={"category": "GREETINGS", "sign": "hello", "mode": "practice"},
        files={"video": ("hello.mp4", vid1_bytes, "video/mp4")}
    )
    assert res1.status_code == 200, f"res1 failed: {res1.text}"
    data1 = res1.json()
    score1 = data1["score"]
    print(f"Correct target evaluation 1 (hello -> hello): Score = {score1}, Band = {data1['band']}, Detected = {data1['detected_sign']}")

    # 2. Evaluate Video 2 with correct target ('EMERGENCY', 'fire')
    with open(vid2_path, "rb") as f:
        vid2_bytes = f.read()

    res2 = client.post(
        "/api/evaluate",
        headers=headers,
        data={"category": "EMERGENCY", "sign": "fire", "mode": "practice"},
        files={"video": ("fire.mp4", vid2_bytes, "video/mp4")}
    )
    assert res2.status_code == 200, f"res2 failed: {res2.text}"
    data2 = res2.json()
    score2 = data2["score"]
    print(f"Correct target evaluation 2 (fire -> fire): Score = {score2}, Band = {data2['band']}, Detected = {data2['detected_sign']}")

    # 3. Evaluate Video 1 with WRONG target ('EMERGENCY', 'fire')
    res_wrong = client.post(
        "/api/evaluate",
        headers=headers,
        data={"category": "EMERGENCY", "sign": "fire", "mode": "practice"},
        files={"video": ("hello.mp4", vid1_bytes, "video/mp4")}
    )
    assert res_wrong.status_code == 200, f"res_wrong failed: {res_wrong.text}"
    data_wrong = res_wrong.json()
    score_wrong = data_wrong["score"]
    print(f"Wrong target evaluation (hello -> fire target): Score = {score_wrong}, Band = {data_wrong['band']}, Detected = {data_wrong['detected_sign']}")

    assert score1 >= 70, f"Expected high score for hello with correct target, got {score1}"
    assert score2 >= 70, f"Expected high score for fire with correct target, got {score2}"
    assert score_wrong < score1, f"Expected wrong target score ({score_wrong}) to be clearly lower than correct score ({score1})"
    print(f"Evaluation check passed. Correct: {score1} & {score2}, Wrong: {score_wrong}")

def test_lock_rules_and_quiz_gating():
    """
    Verify the lock rules on the server:
    1. Default config: every category except SENTENCES is accessible, SENTENCES returns 403.
    2. Set ENFORCE_CATEGORY_LOCKS = True and verify that a later category returns 403
       until the previous category has all signs passed AND its quiz passed.
    3. Verify a quiz cannot be started until every sign in that category is passed.
    4. Restore default config.
    """
    print("\n--- RUNNING TEST: test_lock_rules_and_quiz_gating ---")
    
    # Register a new user
    import uuid
    uname = f"lock_test_{uuid.uuid4().hex[:6]}"
    reg = client.post("/api/auth/register", json={"username": uname, "password": "password123"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Default config check
    assert config.ENFORCE_CATEGORY_LOCKS is False
    res_tut_open = client.get("/api/tutorial/GREETINGS/Hello", headers=headers)
    assert res_tut_open.status_code in [200, 206]

    res_sentences = client.get("/api/tutorial/SENTENCES/Test", headers=headers)
    assert res_sentences.status_code == 403
    print("Default config test passed: Accessible categories are open; SENTENCES returns 403.")

    # 2. Quiz gating check: cannot start quiz before passing all signs
    quiz_res = client.post("/api/quiz/start", headers=headers, json={"category": "GREETINGS"})
    assert quiz_res.status_code == 403, "Quiz should return 403 when signs are not passed"
    print("Quiz gate test passed: Quiz cannot start before all signs passed.")

    # 3. Enable sequential locks
    try:
        config.ENFORCE_CATEGORY_LOCKS = True
        
        # In sequential lock, ALPHABETS is 1st (open), NUMBERS is 2nd (locked because ALPHABETS not passed)
        res_cat2 = client.get("/api/tutorial/NUMBERS/0 one", headers=headers)
        assert res_cat2.status_code == 403, f"Expected 403 for locked category, got {res_cat2.status_code}"
        print(f"Sequential lock verified: Later category returned 403 with reason.")

        # Lessons endpoint should report locked = True for NUMBERS
        lessons_res = client.get("/api/lessons", headers=headers)
        cats = lessons_res.json()["categories"]
        first_cat = cats[0]
        second_cat = cats[1]
        assert first_cat["is_locked"] is False
        assert second_cat["is_locked"] is True
        assert "Complete" in second_cat["lock_reason"]
        print(f"Lessons API reports: {first_cat['name']} locked={first_cat['is_locked']}, {second_cat['name']} locked={second_cat['is_locked']} ('{second_cat['lock_reason']}')")

    finally:
        # Restore default
        config.ENFORCE_CATEGORY_LOCKS = False
        print("Restored config.ENFORCE_CATEGORY_LOCKS = False")

if __name__ == "__main__":
    test_evaluate_with_real_dataset_videos()
    test_lock_rules_and_quiz_gating()

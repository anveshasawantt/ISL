import json
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from zoneinfo import ZoneInfo

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Header,
    Request,
    UploadFile,
    File,
    Form,
    status
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
import numpy as np

import config
from config import (
    COMING_SOON_CATEGORIES,
    ENFORCE_CATEGORY_LOCKS,
    FEEDBACK_BANDS,
    PASS_THRESHOLD,
    QUIZ_PASS_THRESHOLD,
    QUIZ_MAX_QUESTIONS,
    MIRROR_INPUT,
    QUIZ_TEMPORARY_ALL_UNLOCKED,
    QUIZ_ALWAYS_LOCKED_CATEGORIES
)
from database import init_db, get_db
from models import User, Attempt, QuizAttempt, QuizResult
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    get_optional_user
)
from scoring import compute_score
from ml import get_model_and_labels, evaluate_video
from lessons import registry
from streaming import range_requests_response

app = FastAPI(title="ISL Learning App API")

# Initialize database tables immediately
init_db()

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()
    registry.initialize()
    # Warm up model and mediapipe
    get_model_and_labels()

# ----------------- AUTH SCHEMAS & ROUTES -----------------

class AuthRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

@app.post("/api/auth/register", response_model=TokenResponse)
def register(req: AuthRequest, db: Session = Depends(get_db)):
    username = req.username.strip()
    if not username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed = get_password_hash(req.password)
    user = User(username=username, hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer", "username": user.username}

@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: AuthRequest, db: Session = Depends(get_db)):
    username = req.username.strip()
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer", "username": user.username}

@app.get("/api/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username}

# ----------------- LESSONS & STREAMING -----------------

@app.get("/api/lessons")
def get_lessons(
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.id if current_user else 0
    progress = registry.get_user_progress(user_id=user_id, db=db, enforce_locks=config.ENFORCE_CATEGORY_LOCKS)
    return {
        **progress,
        "feedback_bands": FEEDBACK_BANDS,
    }

@app.get("/api/tutorial/{category}/{sign}")
def get_tutorial_video(
    category: str,
    sign: str,
    request: Request,
    range_header: Optional[str] = Header(None, alias="Range"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    if category in COMING_SOON_CATEGORIES:
        raise HTTPException(status_code=403, detail="Category is coming soon")

    user_id = current_user.id if current_user else 0
    progress = registry.get_user_progress(user_id=user_id, db=db, enforce_locks=config.ENFORCE_CATEGORY_LOCKS)

    # Check lock state
    cat_info = next((c for c in progress["categories"] if c["name"] == category), None)
    if not cat_info:
        raise HTTPException(status_code=404, detail="Category not found")
    if cat_info["is_locked"]:
        raise HTTPException(status_code=403, detail=cat_info["lock_reason"] or "Category is locked")

    cat_map = registry.video_files_map.get(category, {})
    video_path = cat_map.get(sign)
    if not video_path:
        # Search case-insensitively
        for s_name, path in cat_map.items():
            if s_name.lower() == sign.lower():
                video_path = path
                break

    if not video_path:
        raise HTTPException(status_code=404, detail="Tutorial video not found")

    return range_requests_response(video_path, range_header)

# ----------------- PRACTICE & QUIZ EVALUATION -----------------

def get_feedback_band_info(score: int) -> dict:
    for band in FEEDBACK_BANDS:
        if band["min"] <= score <= band["max"]:
            return band
    return FEEDBACK_BANDS[0]

@app.post("/api/evaluate")
async def evaluate(
    video: UploadFile = File(...),
    category: str = Form(...),
    sign: str = Form(...),
    mode: str = Form(...),  # "practice" or "quiz"
    quiz_attempt_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if category in COMING_SOON_CATEGORIES:
        raise HTTPException(status_code=403, detail="Category is coming soon")

    progress = registry.get_user_progress(user_id=current_user.id, db=db, enforce_locks=config.ENFORCE_CATEGORY_LOCKS)
    cat_info = next((c for c in progress["categories"] if c["name"] == category), None)
    if not cat_info:
        raise HTTPException(status_code=404, detail="Category not found")
    if cat_info["is_locked"]:
        raise HTTPException(status_code=403, detail=cat_info["lock_reason"] or "Category is locked")

    # If quiz mode, verify quiz is allowed and attempt exists
    if mode == "quiz":
        if not quiz_attempt_id:
            raise HTTPException(status_code=400, detail="quiz_attempt_id required for quiz mode")
        quiz_att = db.query(QuizAttempt).filter(
            QuizAttempt.id == quiz_attempt_id,
            QuizAttempt.user_id == current_user.id
        ).first()
        if not quiz_att:
            raise HTTPException(status_code=404, detail="Quiz attempt not found")
        if quiz_att.status != "in_progress":
            raise HTTPException(status_code=400, detail="Quiz is already completed or inactive")

    # Check if sign has a model
    matched_label = registry.sign_to_model_label.get(category, {}).get(sign)
    if not matched_label:
        # Search case-insensitively or normalized
        from lessons import normalize_text
        norm_sign = normalize_text(sign)
        for s_name, lbl in registry.sign_to_model_label.get(category, {}).items():
            if s_name.lower() == sign.lower() or normalize_text(s_name) == norm_sign:
                matched_label = lbl
                break
            # Also check if model label matches sign
            if lbl:
                _, lbl_s = lbl.split("|")
                if normalize_text(lbl_s) == norm_sign:
                    matched_label = lbl
                    break

    if not matched_label:
        raise HTTPException(status_code=400, detail="No trained model for this sign yet")

    video_bytes = await video.read()
    eval_result = evaluate_video(
        video_bytes=video_bytes,
        filename=video.filename or "recording.webm",
        target_category=category,
        target_sign=sign,
        mirror_input=MIRROR_INPUT
    )

    if "error" in eval_result:
        # Hand check failed (fewer than 10 frames with hands) - do not store attempt
        return {
            "error": eval_result["error"],
            "score": 0,
            "passed": False,
            "feedback_details": {
                "band": "try_again",
                "status_title": "No Hands Detected",
                "summary": "Hands were not clearly detected in the camera frame. Please position both hands visibly and try recording again.",
                "tips": ["Ensure your hands are fully in front of the camera.", "Check lighting conditions in the room."],
                "passed": False
            }
        }

    window_probabilities = eval_result["window_probabilities"]
    labels = eval_result["labels"]
    is_rf = eval_result.get("is_rf", False)

    if is_rf:
        target_idx = eval_result["target_index"]
    else:
        target_idx = eval_result["label_to_index"].get(matched_label)
        if target_idx is None:
            target_idx = 0

    # Compute score using isolated function
    score = compute_score(window_probabilities, target_idx)
    passed = (score >= PASS_THRESHOLD)

    # Determine best window prediction
    window_target_probs = [w[target_idx] for w in window_probabilities]
    best_window_idx = int(np.argmax(window_target_probs))
    best_window_preds = window_probabilities[best_window_idx]
    
    top_class_idx = int(np.argmax(best_window_preds))
    top_label_str = str(labels[top_class_idx])
    if "|" in top_label_str:
        detected_cat, detected_sign = top_label_str.split("|")
    else:
        detected_cat, detected_sign = category, top_label_str

    # Top 3 predictions on the best window
    top3_indices = np.argsort(best_window_preds)[-min(3, len(best_window_preds)):][::-1]
    top3_predictions = [
        {"label": str(labels[i]), "probability": round(float(best_window_preds[i]), 4)}
        for i in top3_indices
    ]

    from scoring import generate_detailed_feedback
    detailed_fb = generate_detailed_feedback(
        score=score,
        target_sign=sign,
        detected_sign=detected_sign,
        top3=top3_predictions,
        category=category
    )

    # Save attempt in database
    attempt = Attempt(
        user_id=current_user.id,
        category=category,
        sign=sign,
        mode=mode,
        score=score,
        passed=passed,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(attempt)

    if mode == "quiz" and quiz_attempt_id:
        quiz_res = QuizResult(
            quiz_attempt_id=quiz_attempt_id,
            sign=sign,
            score=score,
            passed=passed,
            timestamp=datetime.now(timezone.utc)
        )
        db.add(quiz_res)

    db.commit()

    # Recalculate progress
    updated_progress = registry.get_user_progress(user_id=current_user.id, db=db, enforce_locks=config.ENFORCE_CATEGORY_LOCKS)
    updated_cat_info = next((c for c in updated_progress["categories"] if c["name"] == category), None)

    return {
        "score": score,
        "band": detailed_fb["band"],
        "feedback_text": detailed_fb["status_title"],
        "feedback_details": detailed_fb,
        "passed": passed,
        "detected_sign": detected_sign,
        "detected_category": detected_cat,
        "top3": top3_predictions,
        "category_completion": {
            "name": category,
            "signs_passed": updated_cat_info["signs_passed"] if updated_cat_info else 0,
            "total_signs": updated_cat_info["total_signs"] if updated_cat_info else 0,
            "is_completed": updated_cat_info["is_completed"] if updated_cat_info else False,
            "quiz_status": updated_cat_info["quiz_status"] if updated_cat_info else "NOT AVAILABLE",
        },
        "overall_progress": updated_progress["overall_progress"]
    }

# ----------------- QUIZ API -----------------

class StartQuizRequest(BaseModel):
    category: str

@app.post("/api/quiz/start")
def start_quiz(
    req: StartQuizRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    category = req.category
    if category in COMING_SOON_CATEGORIES:
        raise HTTPException(status_code=403, detail="Category is coming soon")

    progress = registry.get_user_progress(user_id=current_user.id, db=db, enforce_locks=config.ENFORCE_CATEGORY_LOCKS)
    cat_info = next((c for c in progress["categories"] if c["name"] == category), None)
    if not cat_info:
        raise HTTPException(status_code=404, detail="Category not found")
    if cat_info["is_locked"]:
        raise HTTPException(status_code=403, detail=cat_info["lock_reason"] or "Category is locked")

    # Quiz available when all signs passed, OR if temporary unlock is active (except BASIC_NEEDS)
    is_temporarily_unlocked = QUIZ_TEMPORARY_ALL_UNLOCKED and (category not in QUIZ_ALWAYS_LOCKED_CATEGORIES)
    if not is_temporarily_unlocked:
        if cat_info["signs_passed"] < cat_info["total_signs"] or cat_info["total_signs"] == 0:
            raise HTTPException(
                status_code=403,
                detail=f"Pass all signs in {category} first before taking the quiz"
            )

    # Get all signs for category
    all_signs = [s["sign"] for s in cat_info["signs"]]
    random.shuffle(all_signs)
    if QUIZ_MAX_QUESTIONS and QUIZ_MAX_QUESTIONS < len(all_signs):
        all_signs = all_signs[:QUIZ_MAX_QUESTIONS]

    quiz_attempt = QuizAttempt(
        user_id=current_user.id,
        category=category,
        questions_json=json.dumps(all_signs),
        status="in_progress",
        created_at=datetime.now(timezone.utc)
    )
    db.add(quiz_attempt)
    db.commit()
    db.refresh(quiz_attempt)

    return {
        "quiz_attempt_id": quiz_attempt.id,
        "category": category,
        "questions": all_signs,
        "total_questions": len(all_signs),
    }

class FinishQuizRequest(BaseModel):
    skipped_signs: Optional[List[str]] = []

@app.post("/api/quiz/{quiz_id}/finish")
def finish_quiz(
    quiz_id: int,
    req: FinishQuizRequest = FinishQuizRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    quiz_attempt = db.query(QuizAttempt).filter(
        QuizAttempt.id == quiz_id,
        QuizAttempt.user_id == current_user.id
    ).first()
    if not quiz_attempt:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    if quiz_attempt.status == "completed":
        # Already completed
        pass

    questions = json.loads(quiz_attempt.questions_json)
    existing_results = db.query(QuizResult).filter(QuizResult.quiz_attempt_id == quiz_id).all()
    answered_map = {r.sign: r.score for r in existing_results}

    # Add skipped questions with 0 score
    for q in questions:
        if q not in answered_map:
            skip_res = QuizResult(
                quiz_attempt_id=quiz_id,
                sign=q,
                score=0,
                passed=False,
                timestamp=datetime.now(timezone.utc)
            )
            db.add(skip_res)
            answered_map[q] = 0

    scores = list(answered_map.values())
    final_score = float(np.mean(scores)) if scores else 0.0
    final_passed = (final_score >= QUIZ_PASS_THRESHOLD)

    quiz_attempt.score = round(final_score, 1)
    quiz_attempt.passed = final_passed
    quiz_attempt.status = "completed"
    quiz_attempt.completed_at = datetime.now(timezone.utc)
    db.commit()

    # Full question breakdown
    breakdown = []
    for q in questions:
        s = answered_map.get(q, 0)
        band = get_feedback_band_info(s)
        breakdown.append({
            "sign": q,
            "score": s,
            "passed": s >= PASS_THRESHOLD,
            "band": band["band"],
            "feedback": band["text"],
        })

    # Updated progress & check unlock
    updated_progress = registry.get_user_progress(user_id=current_user.id, db=db, enforce_locks=ENFORCE_CATEGORY_LOCKS)
    cat_info = next((c for c in updated_progress["categories"] if c["name"] == quiz_attempt.category), None)
    
    # Check what gets unlocked
    next_unlocked = None
    if cat_info and cat_info["is_completed"]:
        # Find the next category in order
        cat_idx = registry.categories.index(quiz_attempt.category)
        if cat_idx + 1 < len(registry.categories):
            next_cat = registry.categories[cat_idx + 1]
            if next_cat not in COMING_SOON_CATEGORIES:
                next_unlocked = next_cat

    band_info = get_feedback_band_info(int(round(final_score)))

    return {
        "quiz_attempt_id": quiz_id,
        "category": quiz_attempt.category,
        "final_score": round(final_score, 1),
        "passed": final_passed,
        "band": band_info["band"],
        "feedback_text": band_info["text"],
        "questions_count": len(questions),
        "breakdown": breakdown,
        "is_completed": cat_info["is_completed"] if cat_info else False,
        "unlocked_category": next_unlocked,
    }

# ----------------- PROFILE API -----------------

@app.get("/api/profile")
def get_profile(
    x_timezone: Optional[str] = Header("UTC", alias="X-Timezone"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_tz = ZoneInfo(x_timezone)
    except Exception:
        user_tz = ZoneInfo("UTC")

    progress = registry.get_user_progress(user_id=current_user.id, db=db, enforce_locks=config.ENFORCE_CATEGORY_LOCKS)

    # Categories completed count
    completed_cats_count = sum(1 for c in progress["categories"] if c.get("is_completed"))

    # Attempts stats
    all_attempts = db.query(Attempt).filter(Attempt.user_id == current_user.id).order_by(Attempt.timestamp.desc()).all()
    total_attempts = len(all_attempts)
    avg_score = round(float(np.mean([a.score for a in all_attempts])), 1) if total_attempts > 0 else 0.0

    # Best quiz score per category
    quiz_attempts = db.query(QuizAttempt).filter(
        QuizAttempt.user_id == current_user.id,
        QuizAttempt.status == "completed"
    ).all()
    best_quiz_scores = {}
    for qa in quiz_attempts:
        if qa.score is not None:
            if qa.category not in best_quiz_scores or qa.score > best_quiz_scores[qa.category]:
                best_quiz_scores[qa.category] = qa.score

    # Streak calculation
    # A day counts when the user has at least one practice or quiz attempt that day in user_tz
    active_dates = set()
    for a in all_attempts:
        if a.timestamp:
            local_dt = a.timestamp.replace(tzinfo=timezone.utc).astimezone(user_tz)
            active_dates.add(local_dt.date())

    for qa in quiz_attempts:
        if qa.completed_at:
            local_dt = qa.completed_at.replace(tzinfo=timezone.utc).astimezone(user_tz)
            active_dates.add(local_dt.date())

    sorted_dates = sorted(list(active_dates))
    current_date = datetime.now(user_tz).date()

    # Compute current streak
    current_streak = 0
    if current_date in active_dates:
        check_date = current_date
        while check_date in active_dates:
            current_streak += 1
            check_date -= timedelta(days=1)
    else:
        # Check yesterday
        yesterday = current_date - timedelta(days=1)
        if yesterday in active_dates:
            check_date = yesterday
            while check_date in active_dates:
                current_streak += 1
                check_date -= timedelta(days=1)

    # Compute longest streak
    longest_streak = 0
    temp_streak = 0
    last_d = None
    for d in sorted_dates:
        if last_d is None or d == last_d + timedelta(days=1):
            temp_streak += 1
        elif d != last_d:
            temp_streak = 1
        longest_streak = max(longest_streak, temp_streak)
        last_d = d

    # 10 most recent activities
    recent_activities = []
    for a in all_attempts[:10]:
        recent_activities.append({
            "id": a.id,
            "category": a.category,
            "sign": a.sign,
            "mode": a.mode,
            "score": a.score,
            "passed": a.passed,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        })

    return {
        "username": current_user.username,
        "signs_learned": progress["total_passed_signs"],
        "total_signs": progress["total_signs"],
        "categories_completed": completed_cats_count,
        "overall_progress": progress["overall_progress"],
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "total_attempts": total_attempts,
        "average_score": avg_score,
        "best_quiz_scores": best_quiz_scores,
        "recent_activities": recent_activities,
    }

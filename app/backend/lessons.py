import os
import re
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
import numpy as np

from config import (
    TUTORIAL_DIR,
    LABELS_PATH,
    CATEGORY_ORDER,
    COMING_SOON_CATEGORIES,
    ENFORCE_CATEGORY_LOCKS,
    QUIZ_GATES_NEXT_CATEGORY,
    PASS_THRESHOLD,
    QUIZ_PASS_THRESHOLD,
    QUIZ_TEMPORARY_ALL_UNLOCKED,
    QUIZ_ALWAYS_LOCKED_CATEGORIES,
)
from models import Attempt, QuizAttempt, QuizResult

def normalize_text(s: str) -> str:
    """Normalize text by lowercasing and stripping spaces, underscores, hyphens, and leading 'ISL '."""
    s = os.path.splitext(s)[0]
    s = re.sub(r'^(isl\s*)', '', s, flags=re.I)
    s = re.sub(r'^(copy of\s*)', '', s, flags=re.I)
    s = re.sub(r'[\s_\-]+', '', s)
    return s.lower()

# Predefined canonical map for common folder spellings
CATEGORY_NAME_MAP = {
    "alphabets": "ALPHABETS",
    "numbers": "NUMBERS",
    "greetings": "GREETINGS",
    "relations": "RELATIONS",
    "peopleandrelations": "RELATIONS",
    "emergency": "EMERGENCY",
    "basicneeds": "BASIC_NEEDS",
    "sentences": "SENTENCES",
}

class LessonRegistry:
    def __init__(self):
        self.categories: List[str] = []
        self.category_lessons: Dict[str, List[Dict[str, Any]]] = {}
        self.model_labels: List[str] = []
        self.model_label_map: Dict[str, Dict[str, int]] = {}  # cat -> {normalized_sign: index}
        self.video_files_map: Dict[str, Dict[str, str]] = {}  # cat -> {sign: abs_video_path}
        self.sign_to_model_label: Dict[str, Dict[str, Optional[str]]] = {}  # cat -> {sign: "CAT|sign" or None}

    def initialize(self):
        # 1. Load model labels
        if os.path.exists(LABELS_PATH):
            self.model_labels = list(np.load(LABELS_PATH))
        else:
            self.model_labels = []

        # Index model labels
        for idx, lbl in enumerate(self.model_labels):
            parts = lbl.split("|")
            cat_name = parts[0]
            sign_name = parts[1]
            cat_norm = normalize_text(cat_name)
            sign_norm = normalize_text(sign_name)

            canon_cat = CATEGORY_NAME_MAP.get(cat_norm, cat_name.upper())
            if canon_cat not in self.model_label_map:
                self.model_label_map[canon_cat] = {}
            self.model_label_map[canon_cat][sign_norm] = idx

        # 2. Scan tutorial directory
        discovered_cat_paths: Dict[str, str] = {}
        # Walk tutorial folder to find video containing subfolders
        for root, dirs, files in os.walk(TUTORIAL_DIR):
            vids = [f for f in files if f.lower().endswith((".mp4", ".mkv", ".avi", ".webm"))]
            if vids:
                folder_name = os.path.basename(root)
                norm_folder = normalize_text(folder_name)
                # Strip trailing 'ok' if present
                norm_folder = re.sub(r'ok$', '', norm_folder)
                canon_cat = CATEGORY_NAME_MAP.get(norm_folder, folder_name.upper())
                discovered_cat_paths[canon_cat] = root

        # 3. Assemble category ordering
        # CATEGORY_ORDER = ["ALPHABETS", "NUMBERS", "GREETINGS", "RELATIONS", "EMERGENCY", "SENTENCES"]
        # Skip names that do not exist in the tutorial folder (except coming-soon categories),
        # and append any other discovered folders before SENTENCES.
        ordered = []
        for cat in CATEGORY_ORDER:
            if cat in COMING_SOON_CATEGORIES:
                continue
            if cat in discovered_cat_paths:
                ordered.append(cat)

        # Append any other discovered folders not in CATEGORY_ORDER before SENTENCES
        for cat in discovered_cat_paths:
            if cat not in ordered and cat not in COMING_SOON_CATEGORIES:
                ordered.append(cat)

        # Append coming soon categories at the end
        for cat in COMING_SOON_CATEGORIES:
            if cat not in ordered:
                ordered.append(cat)

        self.categories = ordered

        # 4. Build lessons per category & matching
        tutorial_without_model = []
        model_without_tutorial = []

        for cat in self.categories:
            self.category_lessons[cat] = []
            self.video_files_map[cat] = {}
            self.sign_to_model_label[cat] = {}

            if cat in COMING_SOON_CATEGORIES:
                continue

            folder_path = discovered_cat_paths.get(cat)
            if not folder_path or not os.path.isdir(folder_path):
                continue

            # List video files
            vids = sorted(
                [f for f in os.listdir(folder_path) if f.lower().endswith((".mp4", ".mkv", ".avi", ".webm"))]
            )

            matched_model_indices = set()
            cat_model_dict = self.model_label_map.get(cat, {})

            for vid in vids:
                stem = os.path.splitext(vid)[0]
                sign_display_name = re.sub(r'^(copy of\s*)', '', stem, flags=re.I).strip()
                sign_norm = normalize_text(stem)

                # Match against model labels
                matched_label_idx = None
                matched_lbl_str = None

                # Direct match
                if sign_norm in cat_model_dict:
                    matched_label_idx = cat_model_dict[sign_norm]
                else:
                    # Try partial match (e.g. 'doctor1' -> 'doctor', '1 one' -> '1')
                    for m_norm, idx in cat_model_dict.items():
                        # exact match after stripping trailing digits
                        norm_no_digits = re.sub(r'\d+$', '', sign_norm)
                        if norm_no_digits == m_norm or sign_norm.startswith(m_norm) or m_norm.startswith(sign_norm):
                            matched_label_idx = idx
                            break

                if matched_label_idx is not None:
                    matched_lbl_str = self.model_labels[matched_label_idx]
                    matched_model_indices.add(matched_label_idx)
                elif cat == "ALPHABETS":
                    # Dedicated Random Forest model for ALPHABETS
                    matched_lbl_str = f"ALPHABETS|{sign_norm.upper()}"
                elif cat == "NUMBERS":
                    # Dedicated Random Forest model for NUMBERS
                    clean_digit = sign_norm.split()[0].upper()
                    matched_lbl_str = f"NUMBERS|{clean_digit}"
                else:
                    tutorial_without_model.append(f"{cat} -> {vid}")

                has_model = (matched_lbl_str is not None)
                self.video_files_map[cat][sign_display_name] = os.path.join(folder_path, vid)
                self.sign_to_model_label[cat][sign_display_name] = matched_lbl_str

                self.category_lessons[cat].append({
                    "sign": sign_display_name,
                    "model_label": matched_lbl_str,
                    "has_model": has_model,
                    "video_path": os.path.join(folder_path, vid),
                })

            # Check model labels with no tutorial video
            for m_norm, idx in cat_model_dict.items():
                if idx not in matched_model_indices:
                    model_without_tutorial.append(self.model_labels[idx])

        # 5. Startup Report
        print("=" * 60)
        print("ISL LESSONS REGISTRY STARTUP REPORT")
        print("=" * 60)
        print(f"Categories loaded in order: {self.categories}")
        print(f"Coming soon categories: {COMING_SOON_CATEGORIES}")
        print(f"\n[Tutorial videos with NO model label] ({len(tutorial_without_model)}):")
        for item in tutorial_without_model:
            print(f"  - {item}")
        print(f"\n[Model labels with NO tutorial video] ({len(model_without_tutorial)}):")
        for item in model_without_tutorial:
            print(f"  - {item}")
        print("=" * 60)

    def get_user_progress(self, user_id: int, db: Session, enforce_locks: bool = ENFORCE_CATEGORY_LOCKS):
        """
        Calculates category and sign progress, lock states, best scores, quiz availability,
        and overall completion for a given user.
        """
        # Load user attempts
        user_attempts = db.query(Attempt).filter(Attempt.user_id == user_id).all()
        # Best score map: (category, sign) -> best_score
        sign_best_scores: Dict[tuple, int] = {}
        sign_attempt_counts: Dict[tuple, int] = {}
        sign_passed_map: Dict[tuple, bool] = {}

        for a in user_attempts:
            key = (a.category, a.sign)
            sign_attempt_counts[key] = sign_attempt_counts.get(key, 0) + 1
            if key not in sign_best_scores or a.score > sign_best_scores[key]:
                sign_best_scores[key] = a.score
            if a.passed or a.score >= PASS_THRESHOLD:
                sign_passed_map[key] = True

        # Load quiz attempts
        quiz_attempts = db.query(QuizAttempt).filter(QuizAttempt.user_id == user_id).all()
        cat_quiz_best: Dict[str, float] = {}
        cat_quiz_passed: Dict[str, bool] = {}

        for qa in quiz_attempts:
            if qa.score is not None:
                if qa.category not in cat_quiz_best or qa.score > cat_quiz_best[qa.category]:
                    cat_quiz_best[qa.category] = qa.score
                if qa.passed or qa.score >= QUIZ_PASS_THRESHOLD:
                    cat_quiz_passed[qa.category] = True

        # Process categories sequentially
        categories_data = []
        total_passed_signs = 0
        total_active_signs = 0
        previous_category_completed = True
        previous_category_name = None

        for cat in self.categories:
            is_coming_soon = cat in COMING_SOON_CATEGORIES
            lessons = self.category_lessons.get(cat, [])

            if is_coming_soon:
                categories_data.append({
                    "name": cat,
                    "is_coming_soon": True,
                    "is_locked": True,
                    "lock_reason": "Coming Soon",
                    "signs_passed": 0,
                    "total_signs": 0,
                    "quiz_status": "NOT AVAILABLE",
                    "quiz_passed": False,
                    "best_quiz_score": None,
                    "is_completed": False,
                    "signs": []
                })
                continue

            signs_data = []
            passed_count = 0
            for lesson in lessons:
                sign_name = lesson["sign"]
                key = (cat, sign_name)
                score = sign_best_scores.get(key, 0)
                passed = sign_passed_map.get(key, False)
                attempts_count = sign_attempt_counts.get(key, 0)

                if passed:
                    passed_count += 1

                signs_data.append({
                    "sign": sign_name,
                    "has_model": lesson["has_model"],
                    "passed": passed,
                    "best_score": score,
                    "attempts_count": attempts_count,
                    "state": "PASSED" if passed else "OPEN",
                })

            total_signs_in_cat = len(signs_data)
            all_signs_passed = (total_signs_in_cat > 0 and passed_count == total_signs_in_cat)
            quiz_passed = cat_quiz_passed.get(cat, False)
            best_quiz = cat_quiz_best.get(cat, None)

            # A category is COMPLETED when:
            # (a) every sign has been passed (best score >= 70) AND
            # (b) category quiz passed (best quiz score >= 70) if QUIZ_GATES_NEXT_CATEGORY is True
            if QUIZ_GATES_NEXT_CATEGORY:
                is_completed = all_signs_passed and quiz_passed
            else:
                is_completed = all_signs_passed

            # Quiz status
            if quiz_passed:
                quiz_status = "PASSED"
            elif all_signs_passed:
                quiz_status = "AVAILABLE"
            elif QUIZ_TEMPORARY_ALL_UNLOCKED and cat not in QUIZ_ALWAYS_LOCKED_CATEGORIES:
                quiz_status = "AVAILABLE"
            else:
                quiz_status = "NOT AVAILABLE"

            # Sequential Lock logic
            if enforce_locks:
                if previous_category_name is None:
                    # First category is always unlocked
                    is_locked = False
                    lock_reason = ""
                else:
                    if previous_category_completed:
                        is_locked = False
                        lock_reason = ""
                    else:
                        is_locked = True
                        lock_reason = f"Complete {previous_category_name} first"
            else:
                is_locked = False
                lock_reason = ""

            total_passed_signs += passed_count
            total_active_signs += total_signs_in_cat

            categories_data.append({
                "name": cat,
                "is_coming_soon": False,
                "is_locked": is_locked,
                "lock_reason": lock_reason,
                "signs_passed": passed_count,
                "total_signs": total_signs_in_cat,
                "quiz_status": quiz_status,
                "quiz_passed": quiz_passed,
                "best_quiz_score": round(best_quiz, 1) if best_quiz is not None else None,
                "is_completed": is_completed,
                "signs": signs_data
            })

            # Update for sequential next category
            previous_category_completed = is_completed
            previous_category_name = cat

        overall_progress = (
            int(round(100.0 * total_passed_signs / total_active_signs))
            if total_active_signs > 0
            else 0
        )

        return {
            "categories": categories_data,
            "overall_progress": overall_progress,
            "total_passed_signs": total_passed_signs,
            "total_signs": total_active_signs,
        }

# Global singleton
registry = LessonRegistry()
registry.initialize()

import numpy as np
from typing import Sequence, Dict, Any, List

def compute_score(window_probabilities: Sequence[np.ndarray], target_index: int) -> int:
    """
    Computes a 0-100 integer score for the target sign based on predictions across sliding windows.
    """
    if len(window_probabilities) == 0:
        return 0

    target_probs = [float(probs[target_index]) for probs in window_probabilities]
    target_probs.sort(reverse=True)
    
    top_k = target_probs[:min(3, len(target_probs))]
    mean_val = float(np.mean(top_k)) if top_k else 0.0
    
    score = int(round(100.0 * mean_val))
    return max(0, min(100, score))


def generate_detailed_feedback(
    score: int,
    target_sign: str,
    detected_sign: str,
    top3: List[Dict[str, Any]],
    category: str
) -> Dict[str, Any]:
    """
    Generates rich, detailed, instructional feedback based on score, target matching,
    hand formation cues, and alternative detections.
    """
    target_clean = target_sign.strip().upper()
    detected_clean = detected_sign.strip().upper() if detected_sign else ""
    is_match = (target_clean == detected_clean)

    tips = []
    summary = ""
    band = ""
    status_title = ""

    if score >= 90:
        band = "excellent"
        status_title = "Spot On! Fantastic Job"
        summary = f"You nailed '{target_clean}'! Your hand shape, palm direction, and movement were clear, steady, and very accurate ({score}%)."
        tips.append("Your gesture timing and hand posture look natural and confident.")
        tips.append("You're ready for the next sign or to challenge yourself on the quiz!")

    elif score >= 70:
        band = "good"
        status_title = "Well Done! Sign Passed"
        if is_match:
            summary = f"Great effort! Your '{target_clean}' sign was recognized with good clarity ({score}%)."
            tips.append("Try holding your hand steady for just half a second longer at the peak of the sign.")
            tips.append("Make sure your palm is facing forward towards the camera as shown in the tutorial.")
        else:
            summary = f"Nice attempt! You passed ({score}%), with just a slight hint of similarity to '{detected_clean}'."
            tips.append(f"To make '{target_clean}' even clearer, double-check your finger spacing compared to '{detected_clean}'.")
            tips.append("Watch the tutorial video at 0.75x speed to catch the subtle hand position details.")

    elif score >= 50:
        band = "practice"
        status_title = "Almost There! Keep Going"
        if is_match:
            summary = f"You're making great progress! We saw '{target_clean}', but your hand moved a bit quickly during recording ({score}%)."
            tips.append("Keep your hands centered in the camera frame from start to finish.")
            tips.append("Take your time: form the sign clearly, hold it firmly for 1-2 seconds, then relax.")
        else:
            alt_info = f" (looked a bit like '{detected_clean}')" if detected_clean else ""
            summary = f"Good try! Your sign wasn't quite clear enough yet{alt_info}. You scored {score}% - just a little more practice to hit the 70% passing mark."
            tips.append(f"Compare your hand and finger positioning with '{target_clean}' in the tutorial.")
            tips.append("Ensure good lighting and check that your hand is clearly visible against your background.")

    else:
        band = "try_again"
        status_title = "Don't Give Up! Let's Try Again"
        if detected_clean and not is_match:
            summary = f"Nice try! It looks like your gesture resembled '{detected_clean}' instead of '{target_clean}'."
            tips.append(f"Watch the tutorial for '{target_clean}' again and notice how each finger is shaped.")
            tips.append("Practice the sign in the mirror or webcam preview once or twice before recording.")
        else:
            summary = f"We couldn't clearly detect the '{target_clean}' sign this time."
            tips.append("Check that your hand is well-lit and stays within the camera frame.")
            tips.append("Start forming your sign 1 second into the recording and hold the shape steadily.")

    # Helpful hint if another sign was prominent
    if len(top3) > 1 and top3[0].get("label") != target_sign:
        alt_label = top3[0].get("label", "").split("|")[-1].upper()
        if alt_label and alt_label != target_clean:
            tips.append(f"Friendly tip: This sign is often confused with '{alt_label}'. Check the lessons list to spot the difference!")

    return {
        "band": band,
        "status_title": status_title,
        "summary": summary,
        "tips": tips,
        "passed": score >= 70,
    }

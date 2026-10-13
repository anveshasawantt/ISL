export interface FeedbackBand {
  min: number;
  max: number;
  text: string;
  band: string;
  color: string;
}

export interface SignData {
  sign: string;
  has_model: boolean;
  passed: boolean;
  best_score: number;
  attempts_count: number;
  state: 'OPEN' | 'PASSED';
}

export interface CategoryData {
  name: string;
  is_coming_soon: boolean;
  is_locked: boolean;
  lock_reason: string;
  signs_passed: number;
  total_signs: number;
  quiz_status: 'NOT AVAILABLE' | 'AVAILABLE' | 'PASSED';
  quiz_passed: boolean;
  best_quiz_score: number | null;
  is_completed: boolean;
  signs: SignData[];
}

export interface LessonsResponse {
  categories: CategoryData[];
  overall_progress: number;
  total_passed_signs: number;
  total_signs: number;
  feedback_bands: FeedbackBand[];
}

export interface PredictionProb {
  label: string;
  probability: number;
}

export interface FeedbackDetails {
  band: string;
  status_title: string;
  summary: string;
  tips: string[];
  passed: boolean;
}

export interface EvaluateResponse {
  score: number;
  band: string;
  feedback_text: string;
  feedback_details?: FeedbackDetails;
  passed: boolean;
  detected_sign: string;
  detected_category: string;
  hands_visible_ratio?: number;
  top3: PredictionProb[];
  error?: string;
  hands_visible_count?: number;
  category_completion?: {
    name: string;
    signs_passed: number;
    total_signs: number;
    is_completed: boolean;
    quiz_status: string;
  };
  overall_progress?: number;
}

export interface QuizQuestionBreakdown {
  sign: string;
  score: number;
  passed: boolean;
  band: string;
  feedback: string;
}

export interface QuizFinishResponse {
  quiz_attempt_id: number;
  category: string;
  final_score: number;
  passed: boolean;
  band: string;
  feedback_text: string;
  questions_count: number;
  breakdown: QuizQuestionBreakdown[];
  is_completed: boolean;
  unlocked_category: string | null;
}

export interface ProfileActivity {
  id: number;
  category: string;
  sign: string;
  mode: string;
  score: number;
  passed: boolean;
  timestamp: string | null;
}

export interface ProfileResponse {
  username: string;
  signs_learned: number;
  total_signs: number;
  categories_completed: number;
  overall_progress: number;
  current_streak: number;
  longest_streak: number;
  total_attempts: number;
  average_score: number;
  best_quiz_scores: Record<string, number>;
  recent_activities: ProfileActivity[];
}

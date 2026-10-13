import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiFetch } from '../services/api';
import type { LessonsResponse, CategoryData, QuizFinishResponse } from '../types';

export const QuizPage: React.FC = () => {
  const { category: paramCat } = useParams<{ category?: string }>();
  const navigate = useNavigate();

  const [lessons, setLessons] = useState<LessonsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Active quiz state
  const [activeCategory, setActiveCategory] = useState<string | null>(paramCat || null);
  const [quizAttemptId, setQuizAttemptId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<string[]>([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState<number>(0);

  // Webcam & Recording
  const [isCameraActive, setIsCameraActive] = useState<boolean>(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const webcamVideoRef = useRef<HTMLVideoElement>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);

  // Recording controls
  const [recordLength, setRecordLength] = useState<number>(10);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [secondsRemaining, setSecondsRemaining] = useState<number>(10);
  const timerIntervalRef = useRef<any>(null);

  // Per question flash & status
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [questionFlash, setQuestionFlash] = useState<{ score: number; band: string; feedback: string } | null>(null);

  // Completed Quiz Results
  const [finalResult, setFinalResult] = useState<QuizFinishResponse | null>(null);

  useEffect(() => {
    loadLessons();
    return () => {
      stopCamera();
      clearInterval(timerIntervalRef.current);
    };
  }, []);

  useEffect(() => {
    if (paramCat) {
      setActiveCategory(paramCat);
    }
  }, [paramCat]);

  const loadLessons = async () => {
    try {
      const data = await apiFetch<LessonsResponse>('/lessons');
      setLessons(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load quiz list');
    } finally {
      setLoading(false);
    }
  };

  const startCamera = async () => {
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false,
      });
      mediaStreamRef.current = stream;
      setIsCameraActive(true);
      if (webcamVideoRef.current) {
        webcamVideoRef.current.srcObject = stream;
        webcamVideoRef.current.play();
      }
    } catch (err: any) {
      setCameraError(
        err.name === 'NotAllowedError'
          ? 'Camera permission denied. Allow webcam in browser.'
          : 'Unable to access camera.'
      );
    }
  };

  const stopCamera = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    setIsCameraActive(false);
  };

  useEffect(() => {
    if (isCameraActive && webcamVideoRef.current && mediaStreamRef.current) {
      webcamVideoRef.current.srcObject = mediaStreamRef.current;
    }
  }, [isCameraActive]);

  const handleStartQuiz = async (catName: string) => {
    setError(null);
    setFinalResult(null);
    setQuestionFlash(null);
    setCurrentQuestionIndex(0);

    try {
      const data = await apiFetch<{
        quiz_attempt_id: number;
        category: string;
        questions: string[];
      }>('/quiz/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: catName }),
      });

      setQuizAttemptId(data.quiz_attempt_id);
      setActiveCategory(data.category);
      setQuestions(data.questions);

      await startCamera();
    } catch (err: any) {
      setError(err.message || 'Could not start quiz');
    }
  };

  const handleRecordQuestion = () => {
    setCountdown(3);
    let count = 3;
    const interval = setInterval(() => {
      count -= 1;
      if (count === 0) {
        clearInterval(interval);
        setCountdown(null);
        startRecordingAudioVisual();
      } else {
        setCountdown(count);
      }
    }, 1000);
  };

  const startRecordingAudioVisual = () => {
    if (!mediaStreamRef.current) return;
    recordedChunksRef.current = [];
    const recorder = new MediaRecorder(mediaStreamRef.current, { mimeType: 'video/webm' });

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        recordedChunksRef.current.push(e.data);
      }
    };

    recorder.onstop = () => {
      const blob = new Blob(recordedChunksRef.current, { type: 'video/webm' });
      submitQuestionAnswer(blob);
    };

    mediaRecorderRef.current = recorder;
    recorder.start(100);
    setIsRecording(true);
    setSecondsRemaining(recordLength);

    let remaining = recordLength;
    timerIntervalRef.current = setInterval(() => {
      remaining -= 1;
      setSecondsRemaining(remaining);
      if (remaining <= 0) {
        stopRecordingSession();
      }
    }, 1000);
  };

  const stopRecordingSession = () => {
    clearInterval(timerIntervalRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  const submitQuestionAnswer = async (blob: Blob) => {
    if (!activeCategory || !quizAttemptId) return;
    setIsAnalyzing(true);

    const targetSign = questions[currentQuestionIndex];
    const formData = new FormData();
    formData.append('video', blob, 'quiz_attempt.webm');
    formData.append('category', activeCategory);
    formData.append('sign', targetSign);
    formData.append('mode', 'quiz');
    formData.append('quiz_attempt_id', quizAttemptId.toString());

    try {
      const token = localStorage.getItem('isl_token');
      const response = await fetch('/api/evaluate', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Question evaluation failed');
      }

      setQuestionFlash({
        score: data.score,
        band: data.band,
        feedback: data.feedback_text,
      });

      setTimeout(() => {
        setQuestionFlash(null);
        goToNextQuestion();
      }, 1500);
    } catch (err: any) {
      setError(err.message || 'Error processing question');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSkipQuestion = () => {
    setQuestionFlash({
      score: 0,
      band: 'try_again',
      feedback: 'SKIPPED (0 PTS)',
    });
    setTimeout(() => {
      setQuestionFlash(null);
      goToNextQuestion();
    }, 1000);
  };

  const goToNextQuestion = () => {
    if (currentQuestionIndex + 1 < questions.length) {
      setCurrentQuestionIndex((prev) => prev + 1);
    } else {
      finishQuiz();
    }
  };

  const finishQuiz = async () => {
    if (!quizAttemptId) return;
    stopCamera();

    try {
      const data = await apiFetch<QuizFinishResponse>(`/quiz/${quizAttemptId}/finish`, {
        method: 'POST',
      });
      setFinalResult(data);
      setQuizAttemptId(null);
      loadLessons();
    } catch (err: any) {
      setError(err.message || 'Error finalizing quiz');
    }
  };

  if (loading) {
    return (
      <div className="p-8 font-bold text-lg uppercase tracking-wider text-gray-500 animate-pulse">
        Loading quiz modules...
      </div>
    );
  }

  // 1. FINAL RESULT SCREEN
  if (finalResult) {
    return (
      <div className="w-full min-h-[calc(100vh-65px)] p-4 sm:p-8 flex flex-col items-center pb-12">
        <div className="w-full max-w-3xl bg-white nb-box p-6 sm:p-8 flex flex-col gap-6">
          <div className="border-b-2 border-[#1A1A24] pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <span className="text-xs font-bold uppercase text-gray-500">QUIZ COMPLETION</span>
              <h1 className="text-2xl sm:text-3xl font-extrabold uppercase tracking-tight">
                {finalResult.category} RESULT
              </h1>
            </div>

            <div
              className={`border-2 border-[#1A1A24] px-5 py-2 font-extrabold text-sm uppercase rounded-lg ${
                finalResult.passed ? 'bg-[#D8F3DC] text-[#1B4332]' : 'bg-[#FFE5D9] text-[#C1121F]'
              }`}
            >
              {finalResult.passed ? 'PASSED (70%+)' : 'NOT PASSED'}
            </div>
          </div>

          <div className="bg-[#FFF3C4] border-2 border-[#1A1A24] rounded-lg p-5 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <span className="text-xs font-bold uppercase text-gray-700">FINAL AVERAGE SCORE</span>
              <div className="text-4xl font-extrabold font-mono text-[#1A1A24]">{finalResult.final_score}%</div>
            </div>
            <div className="text-base font-bold uppercase text-gray-800">{finalResult.feedback_text}</div>
          </div>

          {finalResult.is_completed && (
            <div className="bg-[#D8F3DC] border-2 border-[#1A1A24] rounded-lg p-4 font-bold uppercase text-xs flex flex-col gap-1 text-[#1B4332]">
              <div>CONGRATULATIONS: {finalResult.category} IS NOW FULLY COMPLETED!</div>
              {finalResult.unlocked_category ? (
                <div className="underline">Unlocked next category: {finalResult.unlocked_category}</div>
              ) : (
                <div>All core sign modules mastered!</div>
              )}
            </div>
          )}

          <div>
            <h3 className="text-sm font-extrabold uppercase mb-3">QUESTION BREAKDOWN</h3>
            <div className="border-2 border-[#1A1A24] rounded-lg overflow-hidden">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#1A1A24] text-white text-xs uppercase font-bold">
                    <th className="p-2.5">#</th>
                    <th className="p-2.5">SIGN</th>
                    <th className="p-2.5">SCORE</th>
                    <th className="p-2.5">STATUS</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-xs font-semibold divide-y divide-gray-200">
                  {finalResult.breakdown.map((item, idx) => (
                    <tr key={idx} className={item.passed ? 'bg-green-50/50' : 'bg-red-50/50'}>
                      <td className="p-2.5">{idx + 1}</td>
                      <td className="p-2.5 font-sans font-bold uppercase">{item.sign}</td>
                      <td className="p-2.5 font-bold">{item.score}%</td>
                      <td className="p-2.5 font-sans font-bold uppercase">
                        <span className={item.passed ? 'text-[#2D6A4F]' : 'text-[#C1121F]'}>
                          {item.passed ? 'PASS' : 'FAIL'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-gray-200">
            <button
              onClick={() => handleStartQuiz(finalResult.category)}
              className="nb-btn bg-[#FFF3C4] px-5 py-2 text-xs font-bold uppercase"
            >
              RETAKE QUIZ
            </button>
            <button
              onClick={() => navigate('/')}
              className="nb-btn bg-[#DDF0FF] text-[#1D3557] px-5 py-2 text-xs font-bold uppercase hover:bg-[#BEE1E6]"
            >
              BACK TO DASHBOARD
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 2. QUIZ RUNNING ACTIVE SCREEN
  if (quizAttemptId && questions.length > 0) {
    const currentSign = questions[currentQuestionIndex];
    return (
      <div className="w-full min-h-[calc(100vh-65px)] p-4 sm:p-6 flex flex-col pb-12">
        <div className="bg-white nb-box p-4 mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[10px] font-bold uppercase text-gray-500">QUIZ IN PROGRESS</div>
            <div className="text-lg sm:text-xl font-extrabold uppercase font-mono">
              QUESTION {currentQuestionIndex + 1} / {questions.length} ({activeCategory})
            </div>
          </div>

          <button
            onClick={handleSkipQuestion}
            disabled={isRecording || isAnalyzing}
            className="nb-btn bg-[#FFE5D9] text-[#C1121F] px-4 py-1.5 font-bold text-xs uppercase"
          >
            SKIP QUESTION (0 PTS)
          </button>
        </div>

        {/* Question Prompt */}
        <div className="bg-[#E8E5FA] nb-box p-6 sm:p-8 mb-5 text-center">
          <span className="text-xs font-bold uppercase tracking-wider block text-gray-600 mb-1">
            DEMONSTRATE THE FOLLOWING SIGN IN FRONT OF YOUR WEBCAM
          </span>
          <h1 className="text-5xl sm:text-6xl font-black uppercase tracking-tight text-[#1A1A24]">
            {currentSign}
          </h1>
        </div>

        {/* Webcam Recorder Layout */}
        <div className="w-full max-w-2xl mx-auto bg-white nb-box p-4 flex flex-col items-center">
          {cameraError && (
            <div className="bg-[#FFE5D9] text-[#C1121F] border border-[#1A1A24] p-3 rounded-lg mb-3 font-bold text-xs w-full">
              {cameraError}
            </div>
          )}

          <div className="relative w-full aspect-video bg-neutral-900 border-2 border-[#1A1A24] rounded-lg overflow-hidden flex items-center justify-center">
            {isCameraActive ? (
              <>
                <video
                  ref={webcamVideoRef}
                  autoPlay
                  playsInline
                  muted
                  style={{ transform: 'scaleX(-1)' }}
                  className="w-full h-full object-cover"
                />

                {countdown !== null && (
                  <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center z-20">
                    <span className="text-7xl font-extrabold text-[#FFF3C4] font-mono animate-bounce">
                      {countdown}
                    </span>
                    <span className="text-white font-bold uppercase text-xs mt-2">
                      SIGN NOW!
                    </span>
                  </div>
                )}

                {isRecording && (
                  <div className="absolute top-3 left-3 bg-[#FFE5D9] text-[#C1121F] border border-[#1A1A24] px-3 py-1 rounded font-bold text-xs uppercase flex items-center gap-2">
                    <div className="w-2 h-2 bg-[#C1121F] rounded-full animate-ping" />
                    RECORDING: {secondsRemaining}s REMAINING
                  </div>
                )}

                {isAnalyzing && (
                  <div className="absolute inset-0 bg-black/75 flex flex-col items-center justify-center z-20">
                    <span className="text-3xl font-extrabold text-[#DDF0FF] font-mono animate-pulse">
                      SCORING...
                    </span>
                  </div>
                )}

                {questionFlash && (
                  <div className="absolute inset-0 bg-black/80 flex flex-col items-center justify-center z-30 p-6">
                    <span className="text-6xl font-black font-mono text-white mb-2">
                      {questionFlash.score}%
                    </span>
                    <span
                      className={`px-4 py-1.5 font-bold text-xs uppercase rounded-lg ${
                        questionFlash.score >= 70
                          ? 'bg-[#D8F3DC] text-[#1B4332]'
                          : 'bg-[#FFE5D9] text-[#C1121F]'
                      }`}
                    >
                      {questionFlash.feedback}
                    </span>
                  </div>
                )}
              </>
            ) : (
              <div className="text-white font-bold text-xs uppercase text-center p-4">
                WEBCAM INACTIVE
                <button
                  onClick={startCamera}
                  className="nb-btn bg-[#D8F3DC] text-[#1B4332] px-4 py-1.5 mt-2 block"
                >
                  ENABLE CAMERA
                </button>
              </div>
            )}
          </div>

          {/* Controls Bar */}
          <div className="w-full mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 pt-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase text-gray-500">LENGTH:</span>
              <button
                disabled={isRecording || recordLength <= 5}
                onClick={() => setRecordLength((prev) => Math.max(5, prev - 1))}
                className="nb-btn bg-white px-2 py-0.5 text-xs font-mono font-bold"
              >
                -
              </button>
              <span className="font-mono font-bold text-xs">{recordLength}s</span>
              <button
                disabled={isRecording || recordLength >= 30}
                onClick={() => setRecordLength((prev) => Math.min(30, prev + 1))}
                className="nb-btn bg-white px-2 py-0.5 text-xs font-mono font-bold"
              >
                +
              </button>
            </div>

            {isRecording ? (
              <button
                onClick={stopRecordingSession}
                className="nb-btn bg-[#FFE5D9] text-[#C1121F] px-4 py-1.5 font-bold text-xs uppercase"
              >
                STOP EARLY
              </button>
            ) : (
              <button
                disabled={countdown !== null || isAnalyzing}
                onClick={handleRecordQuestion}
                className="nb-btn bg-[#D8F3DC] text-[#1B4332] px-5 py-2 font-bold text-xs uppercase hover:bg-[#B7E4C7]"
              >
                RECORD ANSWER
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // 3. QUIZ SELECTION LIST (Default /quiz page)
  return (
    <div className="w-full min-h-[calc(100vh-65px)] p-4 sm:p-6 flex flex-col gap-6 pb-12">
      <div className="bg-white nb-box p-5 sm:p-6">
        <h1 className="text-xl sm:text-2xl font-extrabold uppercase tracking-tight">CATEGORY QUIZZES</h1>
        <p className="text-xs font-medium text-gray-600 mt-1">
          Test your mastery after passing all signs in a category (70% or above to pass).
        </p>
      </div>

      {error && (
        <div className="bg-[#FFE5D9] text-[#C1121F] p-4 nb-box font-bold text-xs">
          ERROR: {error}
        </div>
      )}

      {/* Grid of Category Quizzes */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {lessons?.categories.map((cat: CategoryData) => {
          if (cat.is_coming_soon) {
            return (
              <div
                key={cat.name}
                className="hatch-pattern nb-box p-5 opacity-80 select-none flex flex-col justify-between"
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold uppercase">{cat.name}</h2>
                  <span className="bg-[#1A1A24] text-white text-[10px] font-bold px-2 py-0.5 rounded uppercase">
                    COMING SOON
                  </span>
                </div>
                <p className="mt-4 text-xs font-medium text-gray-500">
                  Quiz will unlock once category lessons are released.
                </p>
              </div>
            );
          }

          const isPassed = cat.quiz_status === 'PASSED';
          const isAvailable = cat.quiz_status === 'AVAILABLE' || isPassed;

          return (
            <div
              key={cat.name}
              className={`nb-box p-5 flex flex-col justify-between ${
                isPassed ? 'bg-white' : isAvailable ? 'bg-[#FFF3C4]' : 'bg-[#FBF9F5]'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-lg font-extrabold uppercase">{cat.name}</h2>
                  <span
                    className={`border border-[#1A1A24] text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                      isPassed
                        ? 'bg-[#D8F3DC] text-[#1B4332]'
                        : isAvailable
                        ? 'bg-[#DDF0FF] text-[#1D3557]'
                        : 'bg-white text-gray-600'
                    }`}
                  >
                    {cat.quiz_status}
                  </span>
                </div>

                <div className="text-xs font-medium text-gray-600 mb-3">
                  {cat.signs_passed} / {cat.total_signs} Signs Passed
                </div>

                {!isAvailable && (
                  <div className="text-[11px] font-bold text-[#C1121F] mb-3">
                    Pass all {cat.total_signs} signs first to unlock this quiz.
                  </div>
                )}
              </div>

              {/* Action Button */}
              <div className="pt-3 border-t border-[#1A1A24]/20 flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-gray-700">
                  {cat.best_quiz_score !== null ? `BEST: ${cat.best_quiz_score}%` : 'NO ATTEMPT'}
                </span>

                <button
                  disabled={!isAvailable}
                  onClick={() => handleStartQuiz(cat.name)}
                  className={`nb-btn px-4 py-1.5 text-xs font-bold uppercase ${
                    isPassed
                      ? 'bg-[#FFF3C4] text-[#1A1A24]'
                      : isAvailable
                      ? 'bg-[#D8F3DC] text-[#1B4332]'
                      : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  {isPassed ? 'RETAKE QUIZ' : 'START QUIZ'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

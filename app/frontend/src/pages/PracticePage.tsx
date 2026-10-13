import React, { useEffect, useRef, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiFetch } from '../services/api';
import type { LessonsResponse, EvaluateResponse, SignData } from '../types';

export const PracticePage: React.FC = () => {
  const { category: paramCat, sign: paramSign } = useParams<{ category?: string; sign?: string }>();
  const navigate = useNavigate();

  // Lessons data & selection
  const [lessons, setLessons] = useState<LessonsResponse | null>(null);
  const [currentCategory, setCurrentCategory] = useState<string>('');
  const [currentSign, setCurrentSign] = useState<string>('');
  const [hasModel, setHasModel] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Tutorial video state
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);
  const [isLooping, setIsLooping] = useState<boolean>(true);

  // Webcam & recording state
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

  // Analysis & Evaluation result
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [evalResult, setEvalResult] = useState<EvaluateResponse | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);

  // 1. Initial Load: Fetch lessons and resolve route
  useEffect(() => {
    loadLessons();
  }, [paramCat, paramSign]);

  const loadLessons = async () => {
    try {
      const data = await apiFetch<LessonsResponse>('/lessons');
      setLessons(data);

      if (paramCat && paramSign) {
        setCurrentCategory(paramCat);
        setCurrentSign(decodeURIComponent(paramSign));
        const catObj = data.categories.find((c) => c.name === paramCat);
        const signObj = catObj?.signs.find((s) => s.sign.toLowerCase() === decodeURIComponent(paramSign).toLowerCase());
        setHasModel(signObj ? signObj.has_model : true);
      } else {
        let foundCat = '';
        let foundSign = '';

        for (const cat of data.categories) {
          if (!cat.is_coming_soon && !cat.is_locked) {
            const unpassed = cat.signs.find((s) => !s.passed);
            if (unpassed) {
              foundCat = cat.name;
              foundSign = unpassed.sign;
              break;
            } else if (cat.signs.length > 0 && !foundCat) {
              foundCat = cat.name;
              foundSign = cat.signs[0].sign;
            }
          }
        }

        if (foundCat && foundSign) {
          navigate(`/practice/${foundCat}/${encodeURIComponent(foundSign)}`, { replace: true });
        }
      }
    } catch (err: any) {
      setEvalError(err.message || 'Failed to load lesson details');
    }
  };

  // Search signs within current category or all signs
  const filteredSigns = useMemo(() => {
    if (!lessons) return [];
    if (!searchQuery.trim()) {
      const catObj = lessons.categories.find((c) => c.name === currentCategory);
      return catObj?.signs || [];
    }
    const q = searchQuery.toLowerCase();
    const results: { category: string; sign: SignData }[] = [];
    for (const c of lessons.categories) {
      if (c.is_coming_soon) continue;
      for (const s of c.signs) {
        if (s.sign.toLowerCase().includes(q)) {
          results.push({ category: c.name, sign: s });
        }
      }
    }
    return results;
  }, [lessons, currentCategory, searchQuery]);

  // 2. Camera setup on user trigger
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
          ? 'Camera permission denied. Allow camera in browser settings.'
          : 'Could not access webcam.'
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
    return () => {
      stopCamera();
      clearInterval(timerIntervalRef.current);
    };
  }, []);

  useEffect(() => {
    if (isCameraActive && webcamVideoRef.current && mediaStreamRef.current) {
      webcamVideoRef.current.srcObject = mediaStreamRef.current;
    }
  }, [isCameraActive]);

  // 3. Tutorial Video Controls
  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

  const changeSpeed = (speed: number) => {
    setPlaybackSpeed(speed);
    if (videoRef.current) {
      videoRef.current.playbackRate = speed;
    }
  };

  const toggleLoop = () => {
    setIsLooping(!isLooping);
    if (videoRef.current) {
      videoRef.current.loop = !isLooping;
    }
  };

  // 4. Recording Workflow
  const handleStartRecording = () => {
    setEvalResult(null);
    setEvalError(null);
    setCountdown(3);

    let count = 3;
    const countInterval = setInterval(() => {
      count -= 1;
      if (count === 0) {
        clearInterval(countInterval);
        setCountdown(null);
        beginRecordingSession();
      } else {
        setCountdown(count);
      }
    }, 1000);
  };

  const beginRecordingSession = () => {
    if (!mediaStreamRef.current) return;

    recordedChunksRef.current = [];
    const options = { mimeType: 'video/webm' };
    const recorder = new MediaRecorder(mediaStreamRef.current, options);

    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        recordedChunksRef.current.push(event.data);
      }
    };

    recorder.onstop = () => {
      const blob = new Blob(recordedChunksRef.current, { type: 'video/webm' });
      uploadForEvaluation(blob);
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

  // 5. Upload & Evaluation
  const uploadForEvaluation = async (blob: Blob) => {
    setIsAnalyzing(true);
    setEvalError(null);

    const formData = new FormData();
    formData.append('video', blob, 'practice.webm');
    formData.append('category', currentCategory);
    formData.append('sign', currentSign);
    formData.append('mode', 'practice');

    try {
      const token = localStorage.getItem('isl_token');
      const response = await fetch('/api/evaluate', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Evaluation failed on server');
      }

      setEvalResult(data);
      const refreshed = await apiFetch<LessonsResponse>('/lessons');
      setLessons(refreshed);
    } catch (err: any) {
      setEvalError(err.message || 'Error uploading and processing video');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleNextSign = () => {
    if (!lessons) return;
    const catObj = lessons.categories.find((c) => c.name === currentCategory);
    if (!catObj) return;

    const nextUnpassed = catObj.signs.find((s) => !s.passed && s.sign !== currentSign);
    if (nextUnpassed) {
      navigate(`/practice/${currentCategory}/${encodeURIComponent(nextUnpassed.sign)}`);
    } else {
      const nextAny = catObj.signs.find((s) => s.sign !== currentSign);
      if (nextAny) {
        navigate(`/practice/${currentCategory}/${encodeURIComponent(nextAny.sign)}`);
      }
    }
  };

  const activeCategoryObj = lessons?.categories.find((c) => c.name === currentCategory);
  const isQuizAvailable =
    activeCategoryObj &&
    activeCategoryObj.quiz_status !== 'NOT AVAILABLE';

  return (
    <div className="w-full min-h-[calc(100vh-65px)] flex flex-col p-4 sm:p-6 pb-12">
      {/* Header breadcrumb & Search strip */}
      <div className="bg-white nb-box p-4 mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-[11px] font-bold uppercase text-gray-500">PRACTICE LESSON</div>
          <div className="text-xl sm:text-2xl font-extrabold uppercase tracking-tight flex items-center gap-2">
            <span>{currentCategory}</span>
            <span className="text-gray-400">/</span>
            <span className="text-[#1A1A24] bg-[#FFE5D9] px-2 py-0.5 rounded">{currentSign}</span>
          </div>
        </div>

        {/* Quick Search in Practice */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search sign in lessons..."
              className="px-3 py-1.5 bg-[#FBF9F5] border-2 border-[#1A1A24] rounded-lg text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-[#7B88FF] w-48 sm:w-64"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-1.5 text-[10px] font-bold text-gray-400 hover:text-black"
              >
                ✕
              </button>
            )}

            {/* Dropdown list for matching search results */}
            {searchQuery.trim() && (
              <div className="absolute right-0 top-9 w-64 bg-white border-2 border-[#1A1A24] rounded-lg shadow-lg z-50 max-h-48 overflow-y-auto">
                {(filteredSigns as any[]).map((item) => {
                  const s = item.sign ? item.sign : item;
                  const cat = item.category ? item.category : currentCategory;
                  return (
                    <button
                      key={`${cat}-${s.sign}`}
                      onClick={() => {
                        navigate(`/practice/${cat}/${encodeURIComponent(s.sign)}`);
                        setSearchQuery('');
                      }}
                      className="w-full text-left px-3 py-2 text-xs font-bold hover:bg-[#E8E5FA] border-b border-gray-100 flex items-center justify-between"
                    >
                      <span className="uppercase">{s.sign}</span>
                      <span className="text-[10px] text-gray-400">{cat}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <button
            onClick={() => navigate('/')}
            className="nb-btn bg-[#FFF3C4] px-3.5 py-1.5 font-bold text-xs uppercase"
          >
            DASHBOARD
          </button>
        </div>
      </div>

      {/* Main Split Layout: Tutorial on Left, Practice on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1">
        {/* LEFT COLUMN: Tutorial Video Player */}
        <div className="flex flex-col bg-white nb-box p-4 justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-extrabold uppercase tracking-tight text-[#1A1A24]">
                TUTORIAL DEMONSTRATION
              </h2>
              <span className="text-[10px] font-mono font-bold bg-[#E8E5FA] text-[#1A1A24] border border-[#1A1A24] px-2 py-0.5 rounded uppercase">
                MUTED VIDEO
              </span>
            </div>

            {/* Video Container */}
            <div className="relative w-full aspect-video bg-neutral-900 border-2 border-[#1A1A24] rounded-lg overflow-hidden flex items-center justify-center">
              {currentCategory && currentSign ? (
                <video
                  ref={videoRef}
                  src={`/api/tutorial/${currentCategory}/${encodeURIComponent(currentSign)}`}
                  muted
                  autoPlay
                  loop={isLooping}
                  playsInline
                  controlsList="nodownload"
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  className="w-full h-full object-contain pointer-events-none"
                />
              ) : (
                <div className="text-white font-bold text-xs">SELECT A LESSON TO LOAD VIDEO</div>
              )}
            </div>

            {/* Custom Pastel Video Controls */}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 pt-3">
              <button
                onClick={togglePlay}
                className="nb-btn bg-[#FFF3C4] px-4 py-1 text-xs font-bold"
              >
                {isPlaying ? 'PAUSE' : 'PLAY'}
              </button>

              {/* Playback speed selector */}
              <div className="flex items-center gap-1">
                <span className="text-[11px] font-bold uppercase text-gray-500 mr-1">SPEED:</span>
                {[0.25, 0.5, 0.75, 1, 1.25, 1.5].map((speed) => (
                  <button
                    key={speed}
                    onClick={() => changeSpeed(speed)}
                    className={`nb-btn px-2 py-0.5 text-[10px] font-mono font-bold ${
                      playbackSpeed === speed
                        ? 'bg-[#1A1A24] text-white'
                        : 'bg-white hover:bg-gray-100'
                    }`}
                  >
                    {speed}x
                  </button>
                ))}
              </div>

              {/* Loop Toggle */}
              <button
                onClick={toggleLoop}
                className={`nb-btn px-3 py-1 text-[11px] font-bold ${
                  isLooping ? 'bg-[#D8F3DC] text-[#1B4332]' : 'bg-gray-200 text-gray-600'
                }`}
              >
                LOOP: {isLooping ? 'ON' : 'OFF'}
              </button>
            </div>
          </div>

          {/* Under video: Big Practice activation button if camera off */}
          {!isCameraActive && (
            <div className="mt-5">
              <button
                onClick={startCamera}
                className="nb-btn bg-[#D8F3DC] text-[#1B4332] w-full py-3.5 text-sm font-extrabold tracking-wide hover:bg-[#B7E4C7]"
              >
                START CAMERA FOR PRACTICE
              </button>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Practice Recording & Result Panel */}
        <div className="flex flex-col bg-white nb-box p-4 justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-extrabold uppercase tracking-tight text-[#1A1A24]">
                CAMERA & EVALUATION
              </h2>
              {isCameraActive && (
                <span className="bg-[#D8F3DC] text-[#1B4332] border border-[#1A1A24] text-[10px] font-bold px-2 py-0.5 rounded uppercase">
                  LIVE FEED
                </span>
              )}
            </div>

            {/* Camera Permission or Access Error */}
            {cameraError && (
              <div className="bg-[#FFE5D9] text-[#C1121F] border-2 border-[#1A1A24] p-3 rounded-lg mb-3 font-bold text-xs">
                {cameraError}
                <button
                  onClick={startCamera}
                  className="nb-btn bg-white text-black px-3 py-1 text-xs font-bold ml-3"
                >
                  RETRY CAMERA
                </button>
              </div>
            )}

            {/* Webcam Preview Area */}
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

                  {/* 3-2-1 Countdown Overlay */}
                  {countdown !== null && (
                    <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center z-20">
                      <span className="text-7xl font-extrabold text-[#FFF3C4] font-mono animate-bounce">
                        {countdown}
                      </span>
                      <span className="text-white font-bold uppercase text-xs mt-2">
                        PREPARE YOUR SIGN
                      </span>
                    </div>
                  )}

                  {/* Recording In-Progress Banner */}
                  {isRecording && (
                    <div className="absolute top-3 left-3 bg-[#FFE5D9] text-[#C1121F] border border-[#1A1A24] px-3 py-1 rounded font-bold text-xs uppercase flex items-center gap-2">
                      <div className="w-2 h-2 bg-[#C1121F] rounded-full animate-ping" />
                      RECORDING: {secondsRemaining}s LEFT
                    </div>
                  )}

                  {/* Analysing Loading Overlay */}
                  {isAnalyzing && (
                    <div className="absolute inset-0 bg-black/75 flex flex-col items-center justify-center z-20 p-6 text-center">
                      <div className="text-3xl font-extrabold text-[#DDF0FF] font-mono mb-2 animate-pulse">
                        EVALUATING GESTURE...
                      </div>
                      <p className="text-gray-300 font-medium text-xs">
                        Extracting landmark positions & scoring against model
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <div className="flex flex-col items-center justify-center text-center p-6">
                  <div className="text-gray-400 font-bold text-sm uppercase mb-1">
                    CAMERA OFF
                  </div>
                  <p className="text-gray-500 font-medium text-xs max-w-xs">
                    Press "START CAMERA FOR PRACTICE" to turn on webcam recording.
                  </p>
                </div>
              )}
            </div>

            {/* Recording Controls */}
            {isCameraActive && !isAnalyzing && (
              <div className="mt-3 flex flex-col gap-2.5 border-t border-gray-200 pt-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  {/* Stepper */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase text-gray-600">LENGTH:</span>
                    <button
                      disabled={isRecording || recordLength <= 5}
                      onClick={() => setRecordLength((prev) => Math.max(5, prev - 1))}
                      className="nb-btn bg-white px-2 py-0.5 text-xs font-mono font-bold"
                    >
                      -
                    </button>
                    <span className="font-mono font-bold text-xs px-1">{recordLength}s</span>
                    <button
                      disabled={isRecording || recordLength >= 30}
                      onClick={() => setRecordLength((prev) => Math.min(30, prev + 1))}
                      className="nb-btn bg-white px-2 py-0.5 text-xs font-mono font-bold"
                    >
                      +
                    </button>
                  </div>

                  {/* Record or Stop Early Button */}
                  {isRecording ? (
                    <button
                      onClick={stopRecordingSession}
                      className="nb-btn bg-[#FFE5D9] text-[#C1121F] px-4 py-1.5 font-bold text-xs uppercase"
                    >
                      STOP EARLY
                    </button>
                  ) : (
                    <button
                      disabled={!hasModel || countdown !== null}
                      onClick={handleStartRecording}
                      className="nb-btn bg-[#DDF0FF] text-[#1D3557] px-5 py-1.5 font-bold text-xs uppercase hover:bg-[#BEE1E6]"
                    >
                      RECORD SIGN
                    </button>
                  )}
                </div>

                {isRecording && (
                  <div className="w-full h-2 bg-gray-100 border border-[#1A1A24] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#E63946] transition-all"
                      style={{
                        width: `${((recordLength - secondsRemaining) / recordLength) * 100}%`,
                      }}
                    />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* DETAILED EVALUATION RESULTS PANEL */}
          <div className="mt-4">
            {evalError && (
              <div className="bg-[#FFE5D9] text-[#C1121F] border-2 border-[#1A1A24] p-3 rounded-lg font-bold text-xs">
                EVALUATION ERROR: {evalError}
              </div>
            )}

            {evalResult && (
              <div className="nb-box p-4 bg-white">
                {evalResult.error ? (
                  <div className="bg-[#FFE5D9] text-[#C1121F] border border-[#1A1A24] p-3 rounded font-bold text-xs">
                    {evalResult.error}
                  </div>
                ) : (
                  <div>
                    {/* Top Score Banner */}
                    <div className="flex items-center justify-between gap-3 mb-3 pb-3 border-b border-gray-200">
                      <div>
                        <span className="text-[10px] font-bold uppercase text-gray-500">ACCURACY SCORE</span>
                        <div className="text-4xl font-extrabold font-mono tracking-tight text-[#1A1A24]">
                          {evalResult.score}%
                        </div>
                      </div>

                      {/* Status badge */}
                      <div
                        className={`border-2 border-[#1A1A24] px-4 py-1.5 font-extrabold text-xs uppercase rounded-lg ${
                          evalResult.passed
                            ? 'bg-[#D8F3DC] text-[#1B4332]'
                            : evalResult.score >= 50
                            ? 'bg-[#FFF3C4] text-[#744210]'
                            : 'bg-[#FFE5D9] text-[#C1121F]'
                        }`}
                      >
                        {evalResult.feedback_details?.status_title || evalResult.feedback_text}
                      </div>
                    </div>

                    {/* Detailed Instructional Feedback */}
                    <div className="bg-[#FBF9F5] border border-[#1A1A24]/30 rounded-lg p-3 mb-3 text-xs flex flex-col gap-2">
                      <div className="font-semibold text-gray-800">
                        {evalResult.feedback_details?.summary || (
                          evalResult.passed
                            ? `Great job! Your '${currentSign}' sign was formed accurately.`
                            : `Keep practicing! Ensure your hand shape clearly matches '${currentSign}'.`
                        )}
                      </div>

                      {/* Tips list */}
                      {evalResult.feedback_details?.tips && evalResult.feedback_details.tips.length > 0 && (
                        <div className="pt-2 border-t border-gray-200/80">
                          <span className="text-[10px] font-bold uppercase text-gray-500 block mb-1">
                            COACHING TIPS:
                          </span>
                          <ul className="list-disc list-inside space-y-0.5 text-gray-700">
                            {evalResult.feedback_details.tips.map((tip, idx) => (
                              <li key={idx}>{tip}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* Action buttons on Pass / Fail */}
                    <div className="flex flex-wrap items-center gap-3">
                      {evalResult.passed ? (
                        <>
                          <button
                            onClick={handleNextSign}
                            className="nb-btn bg-[#D8F3DC] text-[#1B4332] px-4 py-2 text-xs font-bold uppercase hover:bg-[#B7E4C7]"
                          >
                            NEXT SIGN
                          </button>

                          {isQuizAvailable && (
                            <div className="w-full mt-2 bg-[#FFF3C4] border border-[#1A1A24] rounded-lg p-3 font-bold text-xs uppercase flex items-center justify-between">
                              <span>QUIZ AVAILABLE FOR {currentCategory}!</span>
                              <button
                                onClick={() => navigate(`/quiz/${currentCategory}`)}
                                className="nb-btn bg-[#DDF0FF] text-[#1D3557] px-3 py-1 text-xs font-bold uppercase"
                              >
                                START QUIZ
                              </button>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="flex items-center justify-between w-full">
                          <span className="text-xs font-bold text-[#C1121F]">
                            Score 70% or above required to pass.
                          </span>
                          <button
                            onClick={handleStartRecording}
                            className="nb-btn bg-[#FFF3C4] text-[#1A1A24] px-4 py-1.5 text-xs font-bold uppercase"
                          >
                            TRY AGAIN
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

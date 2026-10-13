import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '../services/api';
import type { LessonsResponse, CategoryData, SignData } from '../types';

export const DashboardPage: React.FC = () => {
  const [lessons, setLessons] = useState<LessonsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const navigate = useNavigate();

  useEffect(() => {
    fetchLessons();
  }, []);

  const fetchLessons = async () => {
    try {
      setLoading(false);
      const data = await apiFetch<LessonsResponse>('/lessons');
      setLessons(data);
      if (!selectedCategory) {
        const firstActive = data.categories.find((c) => !c.is_coming_soon && !c.is_locked);
        if (firstActive) {
          setSelectedCategory(firstActive.name);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load lessons');
    } finally {
      setLoading(false);
    }
  };

  const activeCategory = lessons?.categories.find((c) => c.name === selectedCategory);

  // Global search across all signs
  const globalSearchResults = useMemo(() => {
    if (!lessons || !searchQuery.trim()) return null;
    const query = searchQuery.trim().toLowerCase();
    const results: { category: string; sign: SignData }[] = [];

    for (const cat of lessons.categories) {
      if (cat.is_coming_soon) continue;
      for (const s of cat.signs) {
        if (s.sign.toLowerCase().includes(query)) {
          results.push({ category: cat.name, sign: s });
        }
      }
    }
    return results;
  }, [lessons, searchQuery]);

  if (loading) {
    return (
      <div className="p-8 font-bold text-lg uppercase tracking-wider text-gray-600 animate-pulse">
        Loading curriculum...
      </div>
    );
  }

  if (error || !lessons) {
    return (
      <div className="p-8 max-w-xl mx-auto">
        <div className="bg-[#FFE5D9] text-[#C1121F] p-4 nb-box font-bold">
          Error loading dashboard: {error || 'Unknown error'}
        </div>
        <button onClick={fetchLessons} className="nb-btn bg-[#FFF3C4] px-4 py-2 mt-4 font-bold">
          RETRY
        </button>
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col min-h-[calc(100vh-65px)] pb-12">
      {/* Top Strip: Overall Progress Bar and Signs Count */}
      <section className="w-full bg-[#E8E5FA]/50 border-b-2 border-[#1A1A24] p-5 sm:p-7">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-3">
          <div>
            <div className="text-xs font-bold uppercase text-gray-600 tracking-wider">
              OVERALL PROGRESS
            </div>
            <div className="text-2xl sm:text-3xl font-extrabold font-mono text-[#1A1A24]">
              {lessons.overall_progress}% MASTERED
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="bg-white border-2 border-[#1A1A24] px-4 py-2 rounded-lg shadow-[2.5px_2.5px_0px_#1A1A24]">
              <span className="text-[10px] font-bold uppercase block text-gray-500">SIGNS PASSED</span>
              <span className="font-mono font-extrabold text-lg">
                {lessons.total_passed_signs} / {lessons.total_signs}
              </span>
            </div>
          </div>
        </div>

        {/* Big Soft-Brutalist Progress Bar with mint accent */}
        <div className="w-full h-5 bg-white border-2 border-[#1A1A24] rounded-full shadow-[2px_2px_0px_#1A1A24] p-0.5 overflow-hidden">
          <div
            className="h-full bg-[#95D5B2] rounded-full transition-all duration-300"
            style={{ width: `${Math.min(100, Math.max(0, lessons.overall_progress))}%` }}
          />
        </div>

        {/* Global Search Bar */}
        <div className="mt-5">
          <div className="relative max-w-xl">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search signs by name (e.g. A, Hello, Doctor, 5)..."
              className="w-full px-4 py-2.5 bg-white border-2 border-[#1A1A24] rounded-lg text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#7B88FF] shadow-[2.5px_2.5px_0px_#1A1A24]"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-2.5 text-xs font-bold text-gray-400 hover:text-black"
              >
                CLEAR
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col p-4 sm:p-6 gap-6">
        {/* If searching globally, render search results */}
        {globalSearchResults !== null ? (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-extrabold uppercase">
                Search Results ({globalSearchResults.length})
              </h2>
              <button
                onClick={() => setSearchQuery('')}
                className="text-xs font-bold underline hover:text-[#7B88FF]"
              >
                BACK TO ALL LESSONS
              </button>
            </div>

            {globalSearchResults.length === 0 ? (
              <div className="bg-white nb-box p-8 text-center font-bold text-gray-500">
                No signs matching "{searchQuery}". Try another keyword.
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {globalSearchResults.map(({ category, sign }) => (
                  <div
                    key={`${category}-${sign.sign}`}
                    onClick={() => navigate(`/practice/${category}/${encodeURIComponent(sign.sign)}`)}
                    className={`nb-box p-3 cursor-pointer select-none transition-all flex flex-col justify-between ${
                      sign.passed
                        ? 'bg-[#D8F3DC] hover:bg-[#B7E4C7]'
                        : 'bg-white hover:bg-[#FFF3C4]'
                    }`}
                  >
                    <div>
                      <div className="text-[10px] font-bold uppercase text-gray-500">{category}</div>
                      <div className="font-extrabold text-sm uppercase truncate" title={sign.sign}>
                        {sign.sign}
                      </div>
                    </div>

                    <div className="mt-3 pt-2 border-t-2 border-[#1A1A24] flex items-center justify-between text-xs">
                      <span className="font-mono font-bold">
                        {sign.passed ? `BEST: ${sign.best_score}%` : 'OPEN'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            {/* Categories List */}
            <div>
              <h2 className="text-lg sm:text-xl font-extrabold uppercase mb-3">CATEGORIES</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {lessons.categories.map((cat: CategoryData) => {
                  const isSelected = selectedCategory === cat.name;

                  // Coming Soon Card
                  if (cat.is_coming_soon) {
                    return (
                      <div
                        key={cat.name}
                        className="hatch-pattern nb-box p-4 opacity-80 cursor-not-allowed select-none flex flex-col justify-between"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-lg uppercase tracking-tight">{cat.name}</span>
                          <span className="bg-[#1A1A24] text-white px-2 py-0.5 rounded text-[10px] font-extrabold">
                            COMING SOON
                          </span>
                        </div>
                        <div className="mt-3 text-[11px] font-semibold text-gray-600 uppercase">
                          New lessons under development
                        </div>
                      </div>
                    );
                  }

                  // Locked Category Card
                  if (cat.is_locked) {
                    return (
                      <div
                        key={cat.name}
                        className="hatch-pattern nb-box p-4 select-none flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-lg uppercase tracking-tight">{cat.name}</span>
                            <span className="bg-[#FFE5D9] text-[#C1121F] border border-[#1A1A24] px-2 py-0.5 rounded text-[10px] font-extrabold">
                              LOCKED
                            </span>
                          </div>
                          <p className="text-[11px] font-bold text-[#C1121F] mt-1.5 uppercase">
                            {cat.lock_reason || 'Complete previous category'}
                          </p>
                        </div>
                        <div className="mt-3 pt-2 border-t border-gray-400 font-mono text-[11px] font-semibold">
                          {cat.signs_passed} / {cat.total_signs} SIGNS
                        </div>
                      </div>
                    );
                  }

                  // Active Category Card
                  const pct = cat.total_signs > 0 ? Math.round((cat.signs_passed / cat.total_signs) * 100) : 0;
                  const allSignsPassed = cat.signs_passed === cat.total_signs && cat.total_signs > 0;

                  return (
                    <div
                      key={cat.name}
                      onClick={() => setSelectedCategory(cat.name)}
                      className={`nb-box p-4 cursor-pointer transition-all flex flex-col justify-between ${
                        isSelected
                          ? 'bg-[#FFF3C4] shadow-[5px_5px_0px_#1A1A24]'
                          : 'bg-white hover:bg-[#FBF9F5]'
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-extrabold text-lg uppercase tracking-tight">{cat.name}</span>
                          {cat.is_completed ? (
                            <span className="bg-[#D8F3DC] text-[#1B4332] border border-[#1A1A24] font-bold text-[10px] px-2 py-0.5 rounded">
                              COMPLETED
                            </span>
                          ) : allSignsPassed ? (
                            <span className="bg-[#DDF0FF] text-[#1D3557] border border-[#1A1A24] font-bold text-[10px] px-2 py-0.5 rounded">
                              READY FOR QUIZ
                            </span>
                          ) : (
                            <span className="bg-white border border-[#1A1A24] font-bold text-[10px] px-2 py-0.5 rounded font-mono">
                              {cat.signs_passed}/{cat.total_signs}
                            </span>
                          )}
                        </div>

                        {/* Category mini progress bar */}
                        <div className="w-full h-2.5 bg-gray-100 border border-[#1A1A24] rounded-full mb-3 overflow-hidden">
                          <div
                            className="h-full bg-[#95D5B2] transition-all"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>

                      {/* Quiz Status & Quiz Action Button */}
                      <div className="pt-2 border-t border-[#1A1A24]/20 flex items-center justify-between">
                        <div className="text-[11px] font-bold uppercase text-gray-700">
                          QUIZ:{' '}
                          <span className={cat.quiz_status === 'PASSED' ? 'text-[#2D6A4F]' : cat.quiz_status === 'AVAILABLE' ? 'text-[#1D3557]' : 'text-gray-600'}>
                            {cat.quiz_status}
                            {cat.best_quiz_score !== null && ` (${cat.best_quiz_score}%)`}
                          </span>
                        </div>

                        <button
                          disabled={cat.quiz_status === 'NOT AVAILABLE'}
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/quiz/${cat.name}`);
                          }}
                          className={`nb-btn px-3 py-1 text-[11px] font-bold ${
                            cat.quiz_status !== 'NOT AVAILABLE'
                              ? 'bg-[#DDF0FF] text-[#1D3557] hover:bg-[#BEE1E6]'
                              : 'bg-gray-200 text-gray-500'
                          }`}
                        >
                          QUIZ
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Selected Category Signs Grid */}
            {activeCategory && (
              <div className="mt-2 pt-5 border-t-2 border-[#1A1A24]">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                  <div>
                    <h3 className="text-xl font-extrabold uppercase tracking-tight text-[#1A1A24]">
                      {activeCategory.name} SIGNS
                    </h3>
                    <p className="text-xs font-semibold text-gray-600 uppercase">
                      Select a sign to view video demonstration and practice
                    </p>
                  </div>

                  {activeCategory.quiz_status !== 'NOT AVAILABLE' && (
                    <button
                      onClick={() => navigate(`/quiz/${activeCategory.name}`)}
                      className="nb-btn bg-[#D8F3DC] text-[#1B4332] px-4 py-2 font-bold text-xs uppercase hover:bg-[#B7E4C7]"
                    >
                      TAKE {activeCategory.name} QUIZ
                    </button>
                  )}
                </div>

                {/* Dense grid of signs */}
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  {activeCategory.signs.map((sign) => {
                    const isPassed = sign.passed;
                    return (
                      <div
                        key={sign.sign}
                        onClick={() => navigate(`/practice/${activeCategory.name}/${encodeURIComponent(sign.sign)}`)}
                        className={`nb-box p-3 cursor-pointer select-none transition-all flex flex-col justify-between ${
                          isPassed
                            ? 'bg-[#D8F3DC] hover:bg-[#B7E4C7]'
                            : 'bg-white hover:bg-[#FFF3C4]'
                        }`}
                      >
                        <div>
                          <div className="text-[10px] font-bold uppercase text-gray-500">SIGN</div>
                          <div className="font-extrabold text-sm uppercase truncate" title={sign.sign}>
                            {sign.sign}
                          </div>
                        </div>

                        <div className="mt-3 pt-2 border-t-2 border-[#1A1A24] flex items-center justify-between">
                          <span className="font-mono text-[11px] font-bold">
                            {isPassed ? `BEST: ${sign.best_score}%` : 'OPEN'}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

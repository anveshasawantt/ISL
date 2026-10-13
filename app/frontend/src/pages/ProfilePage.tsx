import React, { useEffect, useState } from 'react';
import { apiFetch } from '../services/api';
import type { ProfileResponse } from '../types';

export const ProfilePage: React.FC = () => {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      const data = await apiFetch<ProfileResponse>('/profile');
      setProfile(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load user profile');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 font-bold text-lg uppercase tracking-wider text-gray-500 animate-pulse">
        Loading profile...
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="p-8 max-w-lg mx-auto">
        <div className="bg-[#FFE5D9] text-[#C1121F] p-4 nb-box font-bold text-xs">
          ERROR: {error || 'Profile not found'}
        </div>
        <button onClick={fetchProfile} className="nb-btn bg-[#FFF3C4] px-4 py-2 mt-4 font-bold text-xs">
          RETRY
        </button>
      </div>
    );
  }

  return (
    <div className="w-full min-h-[calc(100vh-65px)] p-4 sm:p-6 flex flex-col gap-6 pb-12">
      {/* User Header Strip */}
      <div className="bg-white nb-box p-5 sm:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="text-[11px] font-bold uppercase text-gray-500">STUDENT PROFILE</span>
          <h1 className="text-2xl sm:text-3xl font-extrabold uppercase tracking-tight text-[#1A1A24]">
            {profile.username}
          </h1>
        </div>

        {/* Total Completion Pill */}
        <div className="flex items-center gap-4">
          <div className="bg-[#E8E5FA] border-2 border-[#1A1A24] rounded-lg px-4 py-2 shadow-[2px_2px_0px_#1A1A24]">
            <span className="text-[10px] font-bold uppercase block text-gray-600">CURRICULUM MASTERY</span>
            <span className="text-2xl font-extrabold font-mono text-[#1A1A24]">{profile.overall_progress}%</span>
          </div>
        </div>
      </div>

      {/* Stats Summary Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white nb-box p-4">
          <span className="text-[11px] font-bold uppercase text-gray-500">SIGNS LEARNED</span>
          <div className="text-2xl sm:text-3xl font-extrabold font-mono mt-1 text-[#2D6A4F]">
            {profile.signs_learned} / {profile.total_signs}
          </div>
        </div>

        <div className="bg-white nb-box p-4">
          <span className="text-[11px] font-bold uppercase text-gray-500">CATEGORIES FINISHED</span>
          <div className="text-2xl sm:text-3xl font-extrabold font-mono mt-1 text-[#1D3557]">
            {profile.categories_completed}
          </div>
        </div>

        <div className="bg-white nb-box p-4">
          <span className="text-[11px] font-bold uppercase text-gray-500">CURRENT STREAK</span>
          <div className="text-2xl sm:text-3xl font-extrabold font-mono mt-1 text-[#9D0208]">
            {profile.current_streak} DAYS
          </div>
          <span className="text-[10px] font-semibold text-gray-500 block mt-1">
            LONGEST: {profile.longest_streak} DAYS
          </span>
        </div>

        <div className="bg-white nb-box p-4">
          <span className="text-[11px] font-bold uppercase text-gray-500">AVERAGE SCORE</span>
          <div className="text-2xl sm:text-3xl font-extrabold font-mono mt-1 text-[#1A1A24]">
            {profile.average_score}%
          </div>
          <span className="text-[10px] font-semibold text-gray-500 block mt-1">
            {profile.total_attempts} TOTAL ATTEMPTS
          </span>
        </div>
      </div>

      {/* Best Quiz Score per Category */}
      <div className="bg-white nb-box p-5 sm:p-6">
        <h2 className="text-base sm:text-lg font-extrabold uppercase mb-3 text-[#1A1A24]">CATEGORY QUIZ SCORES</h2>
        {Object.keys(profile.best_quiz_scores).length === 0 ? (
          <div className="text-xs font-semibold text-gray-500 py-2">
            No category quizzes completed yet. Complete all signs in a category to unlock quizzes.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {Object.entries(profile.best_quiz_scores).map(([cat, score]) => (
              <div
                key={cat}
                className="bg-[#FBF9F5] border border-[#1A1A24] rounded-lg p-3 flex items-center justify-between shadow-[2px_2px_0px_#1A1A24]"
              >
                <span className="font-bold text-sm uppercase">{cat}</span>
                <span
                  className={`font-mono font-bold text-base ${
                    score >= 70 ? 'text-[#2D6A4F]' : 'text-[#C1121F]'
                  }`}
                >
                  {score}%
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Activity List (10 most recent) */}
      <div className="bg-white nb-box p-5 sm:p-6">
        <h2 className="text-base sm:text-lg font-extrabold uppercase mb-3 text-[#1A1A24]">RECENT ATTEMPTS (LAST 10)</h2>
        {profile.recent_activities.length === 0 ? (
          <div className="text-xs font-semibold text-gray-500 py-2">
            No practice attempts recorded yet.
          </div>
        ) : (
          <div className="border border-[#1A1A24] rounded-lg overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#1A1A24] text-white text-xs uppercase font-bold">
                  <th className="p-3">TIME</th>
                  <th className="p-3">CATEGORY</th>
                  <th className="p-3">SIGN</th>
                  <th className="p-3">MODE</th>
                  <th className="p-3">SCORE</th>
                  <th className="p-3">STATUS</th>
                </tr>
              </thead>
              <tbody className="font-mono text-xs font-semibold divide-y divide-gray-200">
                {profile.recent_activities.map((act) => {
                  const dateStr = act.timestamp ? new Date(act.timestamp).toLocaleDateString() : '-';
                  const timeStr = act.timestamp ? new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
                  return (
                    <tr key={act.id} className={act.passed ? 'bg-green-50/50' : 'bg-red-50/50'}>
                      <td className="p-3 text-gray-600">
                        {dateStr} {timeStr}
                      </td>
                      <td className="p-3 font-sans font-bold uppercase">{act.category}</td>
                      <td className="p-3 font-sans font-bold uppercase">{act.sign}</td>
                      <td className="p-3 uppercase">{act.mode}</td>
                      <td className="p-3 font-bold">{act.score}%</td>
                      <td className="p-3 font-sans font-bold uppercase">
                        <span className={act.passed ? 'text-[#2D6A4F]' : 'text-[#C1121F]'}>
                          {act.passed ? 'PASSED' : 'TRY AGAIN'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

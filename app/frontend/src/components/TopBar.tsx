import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface TopBarProps {
  streak?: number;
}

export const TopBar: React.FC<TopBarProps> = ({ streak = 0 }) => {
  const { username, logout } = useAuth();
  const location = useLocation();

  const navLinks = [
    { label: 'DASHBOARD', path: '/' },
    { label: 'PRACTICE', path: '/practice' },
    { label: 'QUIZ', path: '/quiz' },
    { label: 'PROFILE', path: '/profile' },
  ];

  return (
    <header className="w-full bg-[#E8E5FA] border-b-2 border-[#1A1A24] flex flex-wrap items-center justify-between px-4 sm:px-8 py-3 select-none sticky top-0 z-50">
      {/* Brand logo / title */}
      <div className="flex items-center gap-3">
        <Link to="/" className="text-xl sm:text-2xl font-black tracking-tight text-[#1A1A24] hover:opacity-80">
          ISL LEARN
        </Link>
        <span className="bg-[#1A1A24] text-[#E8E5FA] text-[11px] font-black px-2 py-0.5 rounded tracking-wider">
          ACADEMY
        </span>
      </div>

      {/* Navigation links */}
      <nav className="flex items-center gap-1.5 sm:gap-2 my-1.5 sm:my-0">
        {navLinks.map((link) => {
          const isActive =
            link.path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(link.path);
          return (
            <Link
              key={link.path}
              to={link.path}
              className={`px-3.5 py-1.5 font-bold text-xs sm:text-sm tracking-wide rounded-md border-2 border-[#1A1A24] transition-all ${
                isActive
                  ? 'bg-[#1A1A24] text-white shadow-[2px_2px_0px_#1A1A24]'
                  : 'bg-white text-[#1A1A24] hover:bg-[#FFE5D9] shadow-[2px_2px_0px_#1A1A24]'
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>

      {/* User, Streak & Logout */}
      <div className="flex items-center gap-2.5 sm:gap-3">
        {/* Streak counter with pastel rose */}
        <div className="flex items-center gap-1.5 bg-[#FFD6E0] border-2 border-[#1A1A24] px-3 py-1 font-bold text-xs sm:text-sm rounded-md shadow-[2px_2px_0px_#1A1A24]">
          <span className="text-[#C1121F]">STREAK:</span>
          <span className="font-mono text-sm">{streak} DAYS</span>
        </div>

        {/* User name display */}
        {username && (
          <div className="hidden md:block font-bold text-xs uppercase px-1 text-gray-700">
            <span className="font-mono text-[#1A1A24]">{username}</span>
          </div>
        )}

        {/* Logout button */}
        <button
          onClick={logout}
          className="nb-btn bg-[#FFE5D9] text-[#C1121F] px-3 sm:px-4 py-1 text-xs font-bold hover:bg-[#FFD6E0]"
          title="Logout"
        >
          LOGOUT
        </button>
      </div>
    </header>
  );
};

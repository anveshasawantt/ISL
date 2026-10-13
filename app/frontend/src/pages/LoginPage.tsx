import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!username.trim() || !password) {
      setError('Please enter both username and password');
      return;
    }

    setLoading(true);
    const endpoint = isRegister ? '/api/auth/register' : '/api/auth/login';

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Authentication failed');
      }

      login(data.access_token, data.username);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FBF9F5] flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md bg-white nb-box p-6 sm:p-8">
        <div className="bg-[#E8E5FA] border-2 border-[#1A1A24] rounded-lg p-4 mb-6 shadow-[2px_2px_0px_#1A1A24]">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-center tracking-tight text-[#1A1A24]">
            ISL LEARN
          </h1>
          <p className="text-center font-bold text-xs mt-1 uppercase tracking-wider text-gray-600">
            {isRegister ? 'CREATE YOUR ACCOUNT' : 'LOGIN TO CONTINUE'}
          </p>
        </div>

        {error && (
          <div className="bg-[#FFE5D9] text-[#C1121F] border border-[#1A1A24] rounded-lg p-3 mb-4 font-bold text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full p-2.5 border-2 border-[#1A1A24] rounded-lg font-mono text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#7B88FF]"
              placeholder="e.g. signlearner"
              autoComplete="username"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full p-2.5 border-2 border-[#1A1A24] rounded-lg font-mono text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#7B88FF]"
              placeholder="••••••••"
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="nb-btn bg-[#D8F3DC] text-[#1B4332] py-2.5 px-4 font-extrabold text-sm mt-2 hover:bg-[#B7E4C7]"
          >
            {loading ? 'PROCESSING...' : isRegister ? 'REGISTER NOW' : 'LOGIN'}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-gray-200 text-center">
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister);
              setError(null);
            }}
            className="text-xs font-bold uppercase underline text-gray-600 hover:text-black"
          >
            {isRegister
              ? 'ALREADY HAVE AN ACCOUNT? LOGIN HERE'
              : "DON'T HAVE AN ACCOUNT? REGISTER HERE"}
          </button>
        </div>
      </div>
    </div>
  );
};

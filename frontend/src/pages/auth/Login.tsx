// Login page — email + password sign-in with inline MFA and new-password challenges.

import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { CognitoUser } from 'amazon-cognito-identity-js';
import { useAuth } from '../../context/AuthContext';

export const Login = () => {
  const { login, completeNewPassword, sendMfaCode } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [givenName, setGivenName] = useState('');
  const [familyName, setFamilyName] = useState('');
  const [challengeUser, setChallengeUser] = useState<CognitoUser | null>(null);
  const [challenge, setChallenge] = useState<'none' | 'mfa' | 'newPassword'>('none');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await login(email, password);
      if (result.newPasswordRequired && result.cognitoUser) {
        setChallengeUser(result.cognitoUser);
        setChallenge('newPassword');
      } else if (result.mfaRequired && result.cognitoUser) {
        setChallengeUser(result.cognitoUser);
        setChallenge('mfa');
      } else {
        navigate('/');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleNewPassword = async (e: FormEvent) => {
    e.preventDefault();
    if (!challengeUser) return;
    setError('');
    setLoading(true);
    try {
      await completeNewPassword(challengeUser, newPassword, { given_name: givenName, family_name: familyName });
      navigate('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Password change failed');
    } finally {
      setLoading(false);
    }
  };

  const handleMfa = async (e: FormEvent) => {
    e.preventDefault();
    if (!challengeUser) return;
    setError('');
    setLoading(true);
    try {
      await sendMfaCode(challengeUser, mfaCode);
      navigate('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid code');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="auth-page w-full max-w-sm">
        <div className="text-center mb-8">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" className="w-10 h-10 mx-auto mb-3 animate-icon-glow">
            <circle cx="16" cy="16" r="15" fill="#1e293b" stroke="#334155" strokeWidth="1"/>
            <path d="M16 5 L20 13 L27 15 L20 17 L16 27 L12 17 L5 15 L12 13Z" fill="#38bdf8" className="animate-icon-star"/>
          </svg>
          <h1 className="text-xl font-semibold text-white">Sign in to AirportHub</h1>
          <p className="text-sm text-slate-400 mt-1">Global Operations Dashboard for Airlines Executives</p>
        </div>
        <div className="bg-surface-card border border-slate-700/50 rounded-lg p-6">
          {challenge === 'none' && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Email</label>
                <input data-testid="login-email" type="email" required value={email} onChange={e => setEmail(e.target.value)}
                  className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-accent transition" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Password</label>
                <input data-testid="login-password" type="password" required value={password} onChange={e => setPassword(e.target.value)}
                  className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-accent transition" />
              </div>
              {error && <p className="text-xs text-status-red">{error}</p>}
              <button data-testid="login-submit" type="submit" disabled={loading}
                className="w-full bg-accent hover:bg-accent-dim text-surface font-medium py-2 rounded text-sm transition disabled:opacity-50">
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
            </form>
          )}
          {challenge === 'newPassword' && (
            <form onSubmit={handleNewPassword} className="space-y-4">
              <p className="text-sm text-slate-300">Set a new password to continue</p>
              <div>
                <label className="block text-xs text-slate-400 mb-1">First Name</label>
                <input type="text" required value={givenName} onChange={e => setGivenName(e.target.value)}
                  className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-accent transition" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Last Name</label>
                <input type="text" required value={familyName} onChange={e => setFamilyName(e.target.value)}
                  className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-accent transition" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">New Password</label>
                <input type="password" required value={newPassword} onChange={e => setNewPassword(e.target.value)}
                  className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-accent transition" />
              </div>
              {error && <p className="text-xs text-status-red">{error}</p>}
              <button type="submit" disabled={loading}
                className="w-full bg-accent hover:bg-accent-dim text-surface font-medium py-2 rounded text-sm transition disabled:opacity-50">
                {loading ? 'Updating…' : 'Set password'}
              </button>
            </form>
          )}
          {challenge === 'mfa' && (
            <form onSubmit={handleMfa} className="space-y-4">
              <p className="text-sm text-slate-300">Enter the code from your authenticator app</p>
              <input data-testid="login-mfa-code" type="text" required value={mfaCode} onChange={e => setMfaCode(e.target.value)}
                placeholder="6-digit code" maxLength={6}
                className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 text-center tracking-widest focus:outline-none focus:border-accent transition" />
              {error && <p className="text-xs text-status-red">{error}</p>}
              <button data-testid="login-mfa-submit" type="submit" disabled={loading}
                className="w-full bg-accent hover:bg-accent-dim text-surface font-medium py-2 rounded text-sm transition disabled:opacity-50">
                {loading ? 'Verifying…' : 'Verify'}
              </button>
            </form>
          )}
          <div className="mt-4 text-center text-xs text-slate-400 space-y-1">
            <p><Link to="/signup" className="text-accent hover:underline">Create account</Link></p>
            <p><Link to="/forgot-password" className="text-accent hover:underline">Forgot password?</Link></p>
          </div>
        </div>
      </div>
    </div>
  );
};

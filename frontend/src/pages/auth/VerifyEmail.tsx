// Email verification page — enter 6-digit code sent by Cognito.

import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export const VerifyEmail = () => {
  const { confirmEmail } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const passedEmail = (location.state as { email?: string })?.email ?? '';
  const [email, setEmail] = useState(passedEmail);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await confirmEmail(email, code);
      navigate('/login', { state: { verified: true } });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="auth-page w-full max-w-sm">
        <div className="text-center mb-8">
          <img src="/favicon.svg" alt="" className="w-10 h-10 mx-auto mb-3" />
          <h1 className="text-xl font-semibold text-white">Verify your email</h1>
          <p className="text-sm text-slate-400 mt-1">Enter the code sent to your email</p>
        </div>
        <div className="bg-surface-card border border-slate-700/50 rounded-lg p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {!passedEmail && (
              <div>
                <label className="block text-xs text-slate-400 mb-1">Email</label>
                <input data-testid="verify-email" type="email" required value={email} onChange={e => setEmail(e.target.value)}
                  className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-accent transition" />
              </div>
            )}
            <div>
              <label className="block text-xs text-slate-400 mb-1">Verification Code</label>
              <input data-testid="verify-code" type="text" required value={code} onChange={e => setCode(e.target.value)}
                placeholder="6-digit code" maxLength={6}
                className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 text-center tracking-widest focus:outline-none focus:border-accent transition" />
            </div>
            {error && <p className="text-xs text-status-red">{error}</p>}
            <button data-testid="verify-submit" type="submit" disabled={loading}
              className="w-full bg-accent hover:bg-accent-dim text-surface font-medium py-2 rounded text-sm transition disabled:opacity-50">
              {loading ? 'Verifying…' : 'Verify email'}
            </button>
          </form>
          <p className="mt-4 text-center text-xs text-slate-400">
            <Link to="/login" className="text-accent hover:underline">Back to sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

// Forgot password page — request a reset code via email.

import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export const ForgotPassword = () => {
  const { forgotPassword } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await forgotPassword(email);
      navigate('/reset-password', { state: { email } });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="auth-page w-full max-w-sm">
        <div className="text-center mb-8">
          <img src="/favicon.svg" alt="" className="w-10 h-10 mx-auto mb-3" />
          <h1 className="text-xl font-semibold text-white">Reset your password</h1>
          <p className="text-sm text-slate-400 mt-1">We'll send a verification code to your email</p>
        </div>
        <div className="bg-surface-card border border-slate-700/50 rounded-lg p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Email</label>
              <input data-testid="forgot-email" type="email" required value={email} onChange={e => setEmail(e.target.value)}
                className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-accent transition" />
            </div>
            {error && <p className="text-xs text-status-red">{error}</p>}
            <button data-testid="forgot-submit" type="submit" disabled={loading}
              className="w-full bg-accent hover:bg-accent-dim text-surface font-medium py-2 rounded text-sm transition disabled:opacity-50">
              {loading ? 'Sending…' : 'Send reset code'}
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

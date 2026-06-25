// MFA setup page — generate TOTP secret and verify with authenticator app.

import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { cognito } from '../../utils/cognito';
import { useAuth } from '../../context/AuthContext';

export const MfaSetup = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [secret, setSecret] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const generateSecret = async () => {
    setError('');
    setLoading(true);
    try {
      const s = await cognito.setupTotp();
      setSecret(s);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate secret');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await cognito.verifyTotp(code);
      setSuccess(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  // Build the otpauth URI for authenticator apps
  const otpauthUri = secret
    ? `otpauth://totp/AirportHub:${user?.email ?? ''}?secret=${secret}&issuer=AirportHub`
    : '';

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="auth-page w-full max-w-sm">
        <div className="text-center mb-8">
          <img src="/favicon.svg" alt="" className="w-10 h-10 mx-auto mb-3" />
          <h1 className="text-xl font-semibold text-white">Set up MFA</h1>
          <p className="text-sm text-slate-400 mt-1">Add an extra layer of security</p>
        </div>
        <div className="bg-surface-card border border-slate-700/50 rounded-lg p-6">
          {success ? (
            <div className="text-center space-y-4">
              <p className="text-status-green text-sm">✓ MFA enabled successfully</p>
              <button data-testid="mfa-done" onClick={() => navigate('/')}
                className="w-full bg-accent hover:bg-accent-dim text-surface font-medium py-2 rounded text-sm transition">
                Back to Dashboard
              </button>
            </div>
          ) : !secret ? (
            <div className="text-center space-y-4">
              <p className="text-sm text-slate-300">Use an authenticator app like Google Authenticator or Authy.</p>
              <button data-testid="mfa-generate" onClick={generateSecret} disabled={loading}
                className="w-full bg-accent hover:bg-accent-dim text-surface font-medium py-2 rounded text-sm transition disabled:opacity-50">
                {loading ? 'Generating…' : 'Generate QR Code'}
              </button>
              <button onClick={() => navigate('/')} className="w-full text-xs text-slate-400 hover:text-slate-200 transition">
                Skip for now
              </button>
            </div>
          ) : (
            <form onSubmit={handleVerify} className="space-y-4">
              <div className="text-center">
                <p className="text-xs text-slate-400 mb-2">Scan this with your authenticator app, or enter the key manually:</p>
                <div className="bg-surface rounded p-3 border border-slate-600">
                  <p className="text-xs text-slate-400 mb-1">Manual key:</p>
                  <code className="text-xs text-accent break-all select-all">{secret}</code>
                </div>
                {otpauthUri && (
                  <p className="text-xs text-slate-500 mt-2">
                    Or use URI: <code className="text-xs break-all select-all">{otpauthUri}</code>
                  </p>
                )}
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Verification Code</label>
                <input data-testid="mfa-code" type="text" required value={code} onChange={e => setCode(e.target.value)}
                  placeholder="6-digit code" maxLength={6}
                  className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 text-center tracking-widest focus:outline-none focus:border-accent transition" />
              </div>
              {error && <p className="text-xs text-status-red">{error}</p>}
              <button data-testid="mfa-verify" type="submit" disabled={loading}
                className="w-full bg-accent hover:bg-accent-dim text-surface font-medium py-2 rounded text-sm transition disabled:opacity-50">
                {loading ? 'Verifying…' : 'Enable MFA'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

// Sign-up page — registration with email, name, organization.

import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export const SignUp = () => {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '', confirm: '', givenName: '', familyName: '', organization: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(prev => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirm) { setError('Passwords do not match'); return; }
    setLoading(true);
    try {
      await signup({
        email: form.email, password: form.password,
        givenName: form.givenName, familyName: form.familyName, organization: form.organization,
      });
      navigate('/verify', { state: { email: form.email } });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Sign-up failed');
    } finally {
      setLoading(false);
    }
  };

  const fields: { key: string; label: string; type: string; placeholder?: string }[] = [
    { key: 'givenName', label: 'First Name', type: 'text' },
    { key: 'familyName', label: 'Last Name', type: 'text' },
    { key: 'organization', label: 'Organization', type: 'text', placeholder: 'Company or team name' },
    { key: 'email', label: 'Email', type: 'email' },
    { key: 'password', label: 'Password', type: 'password', placeholder: 'Min 8 chars, upper/lower/number' },
    { key: 'confirm', label: 'Confirm Password', type: 'password' },
  ];

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="auth-page w-full max-w-sm">
        <div className="text-center mb-8">
          <img src="/favicon.svg" alt="" className="w-10 h-10 mx-auto mb-3" />
          <h1 className="text-xl font-semibold text-white">Create your account</h1>
        </div>
        <div className="bg-surface-card border border-slate-700/50 rounded-lg p-6">
          <form onSubmit={handleSubmit} className="space-y-3">
            {fields.map(f => (
              <div key={f.key}>
                <label className="block text-xs text-slate-400 mb-1">{f.label}</label>
                <input data-testid={`signup-${f.key}`} type={f.type} required
                  value={form[f.key as keyof typeof form]} onChange={set(f.key)}
                  placeholder={f.placeholder}
                  className="w-full bg-surface border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-accent transition" />
              </div>
            ))}
            {error && <p className="text-xs text-status-red">{error}</p>}
            <button data-testid="signup-submit" type="submit" disabled={loading}
              className="w-full bg-accent hover:bg-accent-dim text-surface font-medium py-2 rounded text-sm transition disabled:opacity-50">
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>
          <p className="mt-4 text-center text-xs text-slate-400">
            Already have an account? <Link to="/login" className="text-accent hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

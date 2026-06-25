import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../utils/api';
import type { Airport } from '../utils/api';

const inputClass = 'w-full px-4 py-2 bg-surface border border-slate-700 rounded-md text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent';

export const AddAirport = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<Airport>({ iata_code: '', name: '', city: '', country: '', timezone: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.iata_code || !formData.name || !formData.city) { setError('IATA, Name, and City are required'); return; }
    if (formData.iata_code.length !== 3) { setError('IATA code must be exactly 3 characters'); return; }
    try {
      setLoading(true); setError(null);
      await api.createAirport(formData);
      setSuccess(true);
      setTimeout(() => navigate('/airports'), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create airport');
    } finally { setLoading(false); }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  if (success) {
    return (
      <div className="bg-status-green/10 border border-status-green/30 rounded-lg p-8 text-center">
        <div className="text-4xl mb-3">✅</div>
        <h2 className="text-xl font-semibold text-status-green">Airport Created</h2>
        <p className="text-sm text-slate-400 mt-1">Redirecting...</p>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto">
      <section className="bg-surface-card rounded-lg border border-slate-700/50 p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-5">Add Airport</h2>

        {error && (
          <div className="mb-4 bg-status-red/10 border border-status-red/30 rounded-md p-3 text-sm text-status-red">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {[
            { name: 'iata_code', label: 'IATA Code', placeholder: 'ATL', required: true, maxLength: 3, extra: 'uppercase' },
            { name: 'name', label: 'Airport Name', placeholder: 'Hartsfield-Jackson Atlanta International', required: true },
            { name: 'city', label: 'City', placeholder: 'Atlanta', required: true },
            { name: 'country', label: 'Country', placeholder: 'United States' },
            { name: 'timezone', label: 'Timezone', placeholder: 'America/New_York' },
          ].map(({ name, label, placeholder, required, maxLength, extra }) => (
            <div key={name}>
              <label className="block text-xs text-slate-400 mb-1">
                {label} {required && <span className="text-status-red">*</span>}
              </label>
              <input
                type="text"
                name={name}
                value={(formData as unknown as Record<string, string>)[name] || ''}
                onChange={handleChange}
                maxLength={maxLength}
                placeholder={placeholder}
                className={`${inputClass} ${extra === 'uppercase' ? 'uppercase' : ''}`}
                required={required}
              />
            </div>
          ))}

          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={loading} className="flex-1 px-4 py-2.5 bg-accent text-surface text-sm font-medium rounded-md hover:bg-accent-dim transition disabled:opacity-50">
              {loading ? 'Creating...' : 'Create Airport'}
            </button>
            <button type="button" onClick={() => navigate('/airports')} className="px-4 py-2.5 bg-surface-hover text-slate-300 text-sm rounded-md hover:bg-slate-600 transition">
              Cancel
            </button>
          </div>
        </form>
      </section>
    </div>
  );
};

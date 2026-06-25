import { useState, useEffect } from 'react';
import { api } from '../utils/api';
import type { Airport } from '../utils/api';
import { AirportTable } from '../components/AirportTable';

export const AirportList = () => {
  const [airports, setAirports] = useState<Airport[]>([]);
  const [filteredAirports, setFilteredAirports] = useState<Airport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const loadAirports = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getAirports(200);
      setAirports(data);
      setFilteredAirports(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load airports');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAirports(); }, []);

  useEffect(() => {
    const term = searchTerm.toLowerCase();
    setFilteredAirports(
      (term ? airports.filter((a) => a.iata_code.toLowerCase().includes(term) || a.name.toLowerCase().includes(term) || a.city.toLowerCase().includes(term)) : airports)
        .sort((a, b) => a.name.localeCompare(b.name))
    );
  }, [searchTerm, airports]);

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-500">Loading airports...</div>;

  if (error) {
    return (
      <div className="bg-status-red/10 border border-status-red/30 rounded-lg p-6 text-sm">
        <p className="text-status-red">{error}</p>
        <button onClick={loadAirports} className="mt-3 px-4 py-2 bg-status-red text-white text-xs rounded hover:bg-red-500 transition">Retry</button>
      </div>
    );
  }

  return (
    <section className="bg-surface-card rounded-lg border border-slate-700/50 p-5">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-slate-100">Airports</h2>
        <button onClick={loadAirports} className="px-3 py-1.5 text-xs bg-accent/10 text-accent rounded-md hover:bg-accent/20 transition">Refresh</button>
      </div>
      <input
        type="text"
        placeholder="Search by IATA, name, or city..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        className="w-full mb-4 px-4 py-2 bg-surface border border-slate-700 rounded-md text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
      />
      <p className="text-xs text-slate-500 mb-3">Showing {filteredAirports.length} of {airports.length}</p>
      <AirportTable airports={filteredAirports} />
    </section>
  );
};

import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { StatsCard } from '../components/StatsCard';
import { FlightBoard } from '../components/FlightBoard';
import { FlightFilters } from '../components/FlightFilters';
import { useEffect, useState, useCallback, useRef } from 'react';
import { api, flightsApi, crewApi } from '../utils/api';
import type { Flight, FlightStats, FlightFiltersState } from '../utils/api';

export const Home = () => {
  const { loading } = useApp();
  const [stats, setStats] = useState<{ totalAirports: number } | null>(null);
  const [flights, setFlights] = useState<Flight[]>([]);
  const [flightStats, setFlightStats] = useState<FlightStats | null>(null);
  const [flightsLoading, setFlightsLoading] = useState(true);
  const [flightsError, setFlightsError] = useState<string | null>(null);
  const [fetchedAt, setFetchedAt] = useState<string | null>(null);
  const [filters, setFilters] = useState<FlightFiltersState>({ airport: '', status: '', window: '6h' });
  const [airportCodes, setAirportCodes] = useState<string[]>([]);
  const [countdown, setCountdown] = useState(60);
  const [crewStats, setCrewStats] = useState<{ pilots: number; fas: number; assignedPilots: number; assignedFas: number } | null>(null);

  useEffect(() => {
    api.getAirports(300).then((airports) => setAirportCodes(airports.map((a) => a.iata_code).sort())).catch(() => {});
    api.getStats().then((data) => setStats({ totalAirports: data.totalAirports })).catch(() => {});
    Promise.all([crewApi.getPilots({}, 1), crewApi.getFlightAttendants({}, 1)])
      .then(([p, fa]) => {
        setCrewStats({ pilots: p.total_count ?? p.count, fas: fa.total_count ?? fa.count, assignedPilots: 0, assignedFas: 0 });
      }).catch(() => {});
  }, []);

  const fetchFlights = useCallback(async () => {
    setFlightsLoading(true);
    setFlightsError(null);
    try {
      const flightData = await flightsApi.getFlights(filters, 300);
      const flightList = flightData.flights;
      setFlights(flightList);
      setFetchedAt(flightData.fetched_at || null);
      // Compute stats from filtered flights so they match the selected window
      const byStatus: Record<string, number> = {};
      for (const f of flightList) { byStatus[f.status] = (byStatus[f.status] || 0) + 1; }
      setFlightStats({ total: flightList.length, by_status: byStatus, busiest_airports: [] });
    } catch (err) {
      setFlightsError(err instanceof Error ? err.message : 'Failed to load flights');
    } finally {
      setFlightsLoading(false);
    }
  }, [filters]);

  const fetchRef = useRef(fetchFlights);

  useEffect(() => { fetchFlights(); }, [fetchFlights]);

  // Keep fetchRef current so the interval always calls the latest version
  useEffect(() => { fetchRef.current = fetchFlights; }, [fetchFlights]);

  // Auto-refresh every 30 seconds with countdown
  useEffect(() => {
    setCountdown(60);
    const tick = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          fetchRef.current();
          api.getStats().then((data) => setStats({ totalAirports: data.totalAirports })).catch(() => {});
          return 60;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-slate-500">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Overview cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats && <StatsCard title="Airports" value={stats.totalAirports} icon={<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7"><path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>} color="green" />}
        {flightStats && <StatsCard title="Total Flights" value={flightStats.total} icon={<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7"><path d="M2.5 19h19v2h-19v-2zm16.84-3.15c.8.21 1.62-.26 1.84-1.06.21-.8-.26-1.62-1.06-1.84l-5.31-1.42-2.76-9.02L10.12 2v8.28L5.15 8.95l-.93-2.32-1.45-.39v5.17l16.57 4.44z"/></svg>} color="blue" />}
        {crewStats && <StatsCard title="Active Pilots" value={crewStats.pilots} icon={<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7"><path d="M12 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0 12c-5.33 0-8 2.67-8 4v2h16v-2c0-1.33-2.67-4-8-4z"/></svg>} color="green" />}
        {crewStats && <StatsCard title="Active FA" value={crewStats.fas} icon={<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>} color="orange" />}
      </div>

      {/* Flight Board */}
      <section className="bg-surface-card rounded-lg border border-slate-700/50 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-slate-100">Flight Board</h2>
        </div>
        <FlightFilters filters={filters} onFilterChange={setFilters} airports={airportCodes} />
        <div className="mt-4">
          <FlightBoard flights={flights} stats={flightStats} loading={flightsLoading} error={flightsError} fetchedAt={fetchedAt} onRefreshComplete={fetchFlights} />
        </div>
      </section>

      {/* Quick links */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { to: '/airports', icon: '✈️', title: 'View Airports', desc: 'Browse all airports' },
          { to: '/add', icon: '➕', title: 'Add Airport', desc: 'Create a new entry' },
          { to: '/tech', icon: '📊', title: 'Statistics', desc: 'System & DB stats' },
        ].map(({ to, icon, title, desc }) => (
          <Link key={to} to={to} className="bg-surface-card border border-slate-700/50 rounded-lg p-5 hover:border-accent/30 transition group">
            <span className="text-2xl">{icon}</span>
            <h3 className="text-sm font-semibold text-slate-100 mt-2 group-hover:text-accent transition">{title}</h3>
            <p className="text-xs text-slate-400 mt-1">{desc}</p>
          </Link>
        ))}
      </div>

      {/* Auto-refresh timer */}
      <div className="text-center text-xs text-slate-500">
        Auto-refresh in <span className="font-mono text-slate-400">{countdown}s</span>
      </div>
    </div>
  );
};

import { useState } from 'react';
import type { Flight, FlightStats } from '../utils/api';
import { flightsApi } from '../utils/api';
import { StatsCard } from './StatsCard';

interface FlightBoardProps {
  flights: Flight[];
  stats: FlightStats | null;
  loading: boolean;
  error: string | null;
  fetchedAt?: string | null;
  onRefreshComplete?: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  scheduled: 'bg-accent/15 text-accent',
  boarding: 'bg-status-yellow/15 text-status-yellow',
  departed: 'bg-status-green/15 text-status-green',
  arrived: 'bg-status-green/15 text-status-green',
  delayed: 'bg-status-orange/15 text-status-orange',
  cancelled: 'bg-status-red/15 text-status-red',
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function relativeTime(iso: string): string {
  const diff = (new Date(iso).getTime() - Date.now()) / 60000;
  const abs = Math.abs(Math.round(diff));
  if (abs < 1) return 'now';
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  const label = h > 0 ? `${h}h ${m}m` : `${m}m`;
  return diff > 0 ? `in ${label}` : `${label} ago`;
}

export const FlightBoard = ({ flights, stats, loading, error, fetchedAt, onRefreshComplete }: FlightBoardProps) => {
  const [tab, setTab] = useState<'departures' | 'arrivals'>('departures');
  const [page, setPage] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null);
  const PAGE_SIZE = 20;

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshMsg(null);
    try {
      const result = await flightsApi.refreshFlights();
      setRefreshMsg(`✅ ${result.flights_fetched} flights from ${result.airports_processed} airports (${result.cost_estimate})`);
      onRefreshComplete?.();
    } catch (e) {
      setRefreshMsg(`❌ Refresh failed: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      setRefreshing(false);
    }
  };

  if (error) {
    return (
      <div className="bg-status-red/10 border border-status-red/30 rounded-lg p-4 text-status-red text-sm" data-testid="flight-board-error">
        Unable to load flight data: {error}
      </div>
    );
  }

  const departures = flights.filter(f => !(f as any).board_type || (f as any).board_type === 'departure').sort((a, b) => new Date(a.departure_time).getTime() - new Date(b.departure_time).getTime());
  const arrivals = flights.filter(f => !(f as any).board_type || (f as any).board_type === 'arrival').sort((a, b) => new Date(a.arrival_time).getTime() - new Date(b.arrival_time).getTime());
  const all = tab === 'departures' ? departures : arrivals;
  const totalPages = Math.ceil(all.length / PAGE_SIZE);
  const displayed = all.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div data-testid="flight-board">
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
          <StatsCard title="Boarding" value={stats.by_status?.boarding || 0} icon="🟡" color="orange" />
          <StatsCard title="Departed" value={stats.by_status?.departed || 0} icon="✅" color="green" />
          <StatsCard title="Cancelled" value={stats.by_status?.cancelled || 0} icon="🚫" color="red" />
          <StatsCard title="Delayed" value={stats.by_status?.delayed || 0} icon="⚠️" color="orange" />
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-1">
        {(['departures', 'arrivals'] as const).map((t) => (
          <button
            key={t}
            data-testid={`flight-board-${t}-tab`}
            onClick={() => { setTab(t); setPage(0); }}
            className={`px-4 py-2 text-sm rounded-md transition ${
              tab === t ? 'bg-accent/10 text-accent' : 'text-slate-400 hover:text-slate-200 hover:bg-surface-hover'
            }`}
          >
            {t === 'departures' ? `Departures (${departures.length})` : `Arrivals (${arrivals.length})`}
          </button>
        ))}
        </div>
        <div className="flex items-center gap-3">
          {fetchedAt && (
            <span className="text-xs text-slate-500" data-testid="flight-board-fetched-at">
              Data: {new Date(fetchedAt).toLocaleString()}
            </span>
          )}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-status-orange">$$</span>
            <button
              data-testid="flight-board-refresh-button"
              onClick={handleRefresh}
              disabled={refreshing}
              className="px-3 py-1.5 text-xs rounded-md bg-accent/10 text-accent hover:bg-accent/20 disabled:opacity-50 transition"
            >
              {refreshing ? '⏳ Refreshing...' : '🔄 Refresh Live Flights'}
            </button>
          </div>
        </div>
      </div>
      {refreshMsg && (
        <div className="text-xs text-slate-400 mb-3 px-1" data-testid="flight-board-refresh-msg">{refreshMsg}</div>
      )}

      {loading && <div className="text-center py-12 text-slate-500">Loading flights...</div>}

      {!loading && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-xs text-slate-400 uppercase tracking-wider">
                <th className="px-4 py-3 text-left">Flight</th>
                <th className="px-4 py-3 text-left">Airline</th>
                <th className="px-4 py-3 text-left">{tab === 'departures' ? 'To' : 'From'}</th>
                <th className="px-4 py-3 text-left">Time</th>
                <th className="px-4 py-3 text-left">Gate</th>
                <th className="px-4 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((f) => (
                <tr key={f.flight_number} className="border-b border-slate-700/50 hover:bg-surface-hover transition">
                  <td className="px-4 py-3 font-mono font-medium text-slate-100">{f.flight_number}</td>
                  <td className="px-4 py-3 text-slate-300">{f.airline}</td>
                  <td className="px-4 py-3 text-slate-300">
                    <span className="font-mono text-accent">{tab === 'departures' ? f.destination_iata : f.origin_iata}</span>
                    <span className="text-slate-500 ml-2">{tab === 'departures' ? f.destination_city : f.origin_city}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-200 font-mono">
                    {formatTime(tab === 'departures' ? f.departure_time : f.arrival_time)}
                    <span className="ml-2 text-xs text-slate-500">{relativeTime(tab === 'departures' ? f.departure_time : f.arrival_time)}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-300 font-mono">T{f.terminal}/{f.gate}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${STATUS_COLORS[f.status] || ''}`}>
                      {f.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {displayed.length === 0 && <div className="text-center py-12 text-slate-500">No flights found</div>}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-3 border-t border-slate-700/50 mt-2">
              <span className="text-xs text-slate-500">Page {page + 1} of {totalPages}</span>
              <div className="flex gap-2">
                <button onClick={() => setPage(p => p - 1)} disabled={page === 0} className="px-3 py-1 text-xs rounded bg-surface-hover text-slate-300 disabled:opacity-30 hover:bg-slate-600 transition">Prev</button>
                <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1} className="px-3 py-1 text-xs rounded bg-surface-hover text-slate-300 disabled:opacity-30 hover:bg-slate-600 transition">Next</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Crew Management page — tabbed view with pagination and auto-refresh.

import { useState, useEffect, useRef, useCallback } from 'react';
import { crewApi } from '../utils/api';
import type { Pilot, FlightAttendant, Aircraft, CrewAssignment } from '../utils/api';

const TABS = ['Pilots', 'Flight Attendants', 'Aircraft', 'Assignments'] as const;
type Tab = typeof TABS[number];
const PAGE_SIZE = 20;

const fatigueBadge = (status: string) => {
  const colors: Record<string, string> = {
    GREEN: 'bg-status-green/20 text-status-green',
    YELLOW: 'bg-status-orange/20 text-status-orange',
    RED: 'bg-status-red/20 text-status-red',
  };
  return colors[status] || 'bg-slate-700 text-slate-300';
};

export const Crew = () => {
  const [tab, setTab] = useState<Tab>('Pilots');
  const [pilots, setPilots] = useState<Pilot[]>([]);
  const [fas, setFas] = useState<FlightAttendant[]>([]);
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);
  const [assignments, setAssignments] = useState<CrewAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [countdown, setCountdown] = useState(60);

  const loadData = useCallback(async (t: Tab) => {
    setLoading(true);
    setError(null);
    try {
      if (t === 'Pilots') { const d = await crewApi.getPilots({}, 1000); setPilots(d.items); }
      else if (t === 'Flight Attendants') { const d = await crewApi.getFlightAttendants({}, 1000); setFas(d.items); }
      else if (t === 'Aircraft') { const d = await crewApi.getAircraft(); setAircraft(d.items); }
      else { const d = await crewApi.getAssignments({}, 1000); setAssignments(d.items); }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  // Reset page when switching tabs
  const switchTab = (t: Tab) => { setTab(t); setPage(1); };

  // Load data on tab change
  useEffect(() => { loadData(tab); }, [tab, loadData]);

  // Auto-refresh every 60 seconds with countdown
  const loadRef = useRef(loadData);
  const tabRef = useRef(tab);
  useEffect(() => { loadRef.current = loadData; }, [loadData]);
  useEffect(() => { tabRef.current = tab; }, [tab]);

  useEffect(() => {
    setCountdown(60);
    const tick = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) { loadRef.current(tabRef.current); return 60; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [tab]);

  // Pagination helper
  const paginate = <T,>(data: T[]) => {
    const total = Math.ceil(data.length / PAGE_SIZE);
    const sliced = data.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
    return { sliced, total, count: data.length };
  };

  return (
    <div className="space-y-4">
      {/* Tab bar */}
      <div className="flex gap-1 bg-surface-card rounded-lg border border-slate-700/50 p-1">
        {TABS.map((t) => (
          <button key={t} onClick={() => switchTab(t)} data-testid={`crew-tab-${t.toLowerCase().replace(' ', '-')}`}
            className={`flex-1 px-4 py-2 text-sm rounded-md transition ${tab === t ? 'bg-accent text-white' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'}`}>
            {t}
          </button>
        ))}
      </div>

      {/* Content */}
      <section className="bg-surface-card rounded-lg border border-slate-700/50 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-100">{tab}</h2>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">Refresh in {countdown}s</span>
            <button onClick={() => { loadData(tab); setCountdown(60); }} data-testid="crew-refresh"
              className="px-3 py-1.5 text-xs bg-accent/10 text-accent rounded-md hover:bg-accent/20 transition">Refresh</button>
          </div>
        </div>

        {loading && <div className="flex items-center justify-center h-40 text-slate-500">Loading...</div>}
        {error && (
          <div className="bg-status-red/10 border border-status-red/30 rounded-lg p-4 text-sm">
            <p className="text-status-red">{error}</p>
            <button onClick={() => loadData(tab)} className="mt-2 px-3 py-1.5 bg-status-red text-white text-xs rounded hover:bg-red-500 transition">Retry</button>
          </div>
        )}

        {!loading && !error && tab === 'Pilots' && <PilotsTable {...paginate(pilots)} />}
        {!loading && !error && tab === 'Flight Attendants' && <FAsTable {...paginate(fas)} />}
        {!loading && !error && tab === 'Aircraft' && <AircraftTable {...paginate(aircraft)} />}
        {!loading && !error && tab === 'Assignments' && <AssignmentsTable {...paginate(assignments)} />}

        {/* Pagination controls */}
        {!loading && !error && <Pagination page={page} total={Math.ceil(currentCount(tab, pilots, fas, aircraft, assignments) / PAGE_SIZE)} onPage={setPage} />}
      </section>
    </div>
  );
};

// Helper to get current tab's data count
const currentCount = (tab: Tab, pilots: Pilot[], fas: FlightAttendant[], aircraft: Aircraft[], assignments: CrewAssignment[]) => {
  if (tab === 'Pilots') return pilots.length;
  if (tab === 'Flight Attendants') return fas.length;
  if (tab === 'Aircraft') return aircraft.length;
  return assignments.length;
};

// --- Pagination component ---
const Pagination = ({ page, total, onPage }: { page: number; total: number; onPage: (p: number) => void }) => {
  if (total <= 1) return null;
  return (
    <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-700/50">
      <span className="text-xs text-slate-500">Page {page} of {total}</span>
      <div className="flex gap-1">
        <button onClick={() => onPage(Math.max(1, page - 1))} disabled={page === 1} data-testid="crew-page-prev"
          className="px-3 py-1 text-xs rounded bg-slate-700/50 text-slate-300 hover:bg-slate-600 disabled:opacity-30 disabled:cursor-not-allowed transition">Prev</button>
        <button onClick={() => onPage(Math.min(total, page + 1))} disabled={page === total} data-testid="crew-page-next"
          className="px-3 py-1 text-xs rounded bg-slate-700/50 text-slate-300 hover:bg-slate-600 disabled:opacity-30 disabled:cursor-not-allowed transition">Next</button>
      </div>
    </div>
  );
};

// --- Table sub-components (now receive paginated slices) ---

const PilotsTable = ({ sliced, count }: { sliced: Pilot[]; total: number; count: number }) => (
  <div className="overflow-x-auto">
    <p className="text-xs text-slate-500 mb-2">Showing {sliced.length} of {count}</p>
    <table className="w-full text-sm">
      <thead><tr className="text-left text-xs text-slate-500 uppercase border-b border-slate-700">
        <th className="pb-2 pr-4">ID</th><th className="pb-2 pr-4">Name</th><th className="pb-2 pr-4">Designation</th>
        <th className="pb-2 pr-4">Base</th><th className="pb-2 pr-4">Type Ratings</th><th className="pb-2 pr-4">Hours</th><th className="pb-2">Fatigue</th>
      </tr></thead>
      <tbody>
        {sliced.map((p) => (
          <tr key={p.employee_id} className="border-b border-slate-700/50 text-slate-300">
            <td className="py-2 pr-4 font-mono text-xs">{p.employee_id}</td>
            <td className="py-2 pr-4">{p.first_name} {p.last_name}</td>
            <td className="py-2 pr-4">{p.designation}</td>
            <td className="py-2 pr-4 font-mono">{p.base_airport}</td>
            <td className="py-2 pr-4 text-xs">{p.qualifications?.type_ratings?.join(', ') || '—'}</td>
            <td className="py-2 pr-4">{p.qualifications?.total_flight_hours?.toLocaleString() || '—'}</td>
            <td className="py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${fatigueBadge(p.fatigue?.compliance_status)}`}>{p.fatigue?.compliance_status}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
    {sliced.length === 0 && <p className="text-center text-slate-500 py-8">No pilots found</p>}
  </div>
);

const FAsTable = ({ sliced, count }: { sliced: FlightAttendant[]; total: number; count: number }) => (
  <div className="overflow-x-auto">
    <p className="text-xs text-slate-500 mb-2">Showing {sliced.length} of {count}</p>
    <table className="w-full text-sm">
      <thead><tr className="text-left text-xs text-slate-500 uppercase border-b border-slate-700">
        <th className="pb-2 pr-4">ID</th><th className="pb-2 pr-4">Name</th><th className="pb-2 pr-4">Designation</th>
        <th className="pb-2 pr-4">Cert</th><th className="pb-2 pr-4">Base</th><th className="pb-2 pr-4">Languages</th><th className="pb-2">Fatigue</th>
      </tr></thead>
      <tbody>
        {sliced.map((fa) => (
          <tr key={fa.employee_id} className="border-b border-slate-700/50 text-slate-300">
            <td className="py-2 pr-4 font-mono text-xs">{fa.employee_id}</td>
            <td className="py-2 pr-4">{fa.first_name} {fa.last_name}</td>
            <td className="py-2 pr-4">{fa.designation}</td>
            <td className="py-2 pr-4 font-mono">{fa.certification_level}</td>
            <td className="py-2 pr-4 font-mono">{fa.base_airport}</td>
            <td className="py-2 pr-4 text-xs">{fa.languages?.join(', ') || '—'}</td>
            <td className="py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${fatigueBadge(fa.fatigue?.compliance_status)}`}>{fa.fatigue?.compliance_status}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
    {sliced.length === 0 && <p className="text-center text-slate-500 py-8">No flight attendants found</p>}
  </div>
);

const AircraftTable = ({ sliced, count }: { sliced: Aircraft[]; total: number; count: number }) => (
  <div className="overflow-x-auto">
    <p className="text-xs text-slate-500 mb-2">Showing {sliced.length} of {count}</p>
    <table className="w-full text-sm">
      <thead><tr className="text-left text-xs text-slate-500 uppercase border-b border-slate-700">
        <th className="pb-2 pr-4">Type</th><th className="pb-2 pr-4">Category</th><th className="pb-2 pr-4">Seats</th>
        <th className="pb-2 pr-4">Pilots Req</th><th className="pb-2 pr-4">FAs Req</th><th className="pb-2">Range (hrs)</th>
      </tr></thead>
      <tbody>
        {sliced.map((a) => (
          <tr key={a.aircraft_type} className="border-b border-slate-700/50 text-slate-300">
            <td className="py-2 pr-4 font-medium">{a.aircraft_type}</td>
            <td className="py-2 pr-4 capitalize">{a.category}</td>
            <td className="py-2 pr-4">{a.seat_capacity}</td>
            <td className="py-2 pr-4">{a.required_pilots}</td>
            <td className="py-2 pr-4">{a.required_fas}</td>
            <td className="py-2">{a.max_range_hours}</td>
          </tr>
        ))}
      </tbody>
    </table>
    {sliced.length === 0 && <p className="text-center text-slate-500 py-8">No aircraft found</p>}
  </div>
);

const AssignmentsTable = ({ sliced, count }: { sliced: CrewAssignment[]; total: number; count: number }) => (
  <div className="overflow-x-auto">
    <p className="text-xs text-slate-500 mb-2">Showing {sliced.length} of {count}</p>
    <table className="w-full text-sm">
      <thead><tr className="text-left text-xs text-slate-500 uppercase border-b border-slate-700">
        <th className="pb-2 pr-4">Flight</th><th className="pb-2 pr-4">Date</th><th className="pb-2 pr-4">Aircraft</th>
        <th className="pb-2 pr-4">Pilots Assigned</th><th className="pb-2 pr-4">FA Assigned</th><th className="pb-2">Total</th>
      </tr></thead>
      <tbody>
        {sliced.map((a, i) => (
          <tr key={`${a.flight_number}-${i}`} className="border-b border-slate-700/50 text-slate-300 align-top">
            <td className="py-2 pr-4 font-mono font-medium">{a.flight_number}</td>
            <td className="py-2 pr-4">{a.flight_date}</td>
            <td className="py-2 pr-4">{a.aircraft_type}</td>
            <td className="py-2 pr-4 text-xs">{a.assigned_pilots?.map(p => `${p.employee_id} (${p.role})`).join(', ') || '—'}</td>
            <td className="py-2 pr-4 text-xs">{a.assigned_fas?.map(f => `${f.employee_id} (${f.role})`).join(', ') || '—'}</td>
            <td className="py-2">{a.total_crew}</td>
          </tr>
        ))}
      </tbody>
    </table>
    {sliced.length === 0 && <p className="text-center text-slate-500 py-8">No assignments found</p>}
  </div>
);

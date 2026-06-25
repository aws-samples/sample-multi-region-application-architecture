import type { FlightFiltersState } from '../utils/api';

interface FlightFiltersProps {
  filters: FlightFiltersState;
  onFilterChange: (filters: FlightFiltersState) => void;
  airports: string[];
}

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'boarding', label: 'Boarding' },
  { value: 'departed', label: 'Departed' },
  { value: 'arrived', label: 'Arrived' },
  { value: 'delayed', label: 'Delayed' },
  { value: 'cancelled', label: 'Cancelled' },
];

const WINDOW_OPTIONS = [
  { value: '2h' as const, label: '2h' },
  { value: '6h' as const, label: '6h' },
  { value: '24h' as const, label: '24h' },
];

const selectClass = 'bg-surface border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent';

export const FlightFilters = ({ filters, onFilterChange, airports }: FlightFiltersProps) => {
  const update = (patch: Partial<FlightFiltersState>) =>
    onFilterChange({ ...filters, ...patch });

  return (
    <div className="flex flex-wrap gap-3 items-end" data-testid="flight-filters">
      <div>
        <label htmlFor="airport-filter" className="block text-xs text-slate-400 mb-1">Airport</label>
        <select id="airport-filter" data-testid="flight-filters-airport-select" value={filters.airport} onChange={(e) => update({ airport: e.target.value })} className={selectClass}>
          <option value="">All</option>
          {airports.map((code) => <option key={code} value={code}>{code}</option>)}
        </select>
      </div>
      <div>
        <label htmlFor="status-filter" className="block text-xs text-slate-400 mb-1">Status</label>
        <select id="status-filter" data-testid="flight-filters-status-select" value={filters.status} onChange={(e) => update({ status: e.target.value })} className={selectClass}>
          {STATUS_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
      </div>
      <div>
        <label htmlFor="window-filter" className="block text-xs text-slate-400 mb-1">Window</label>
        <select id="window-filter" data-testid="flight-filters-window-select" value={filters.window} onChange={(e) => update({ window: e.target.value as FlightFiltersState['window'] })} className={selectClass}>
          {WINDOW_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
      </div>
    </div>
  );
};

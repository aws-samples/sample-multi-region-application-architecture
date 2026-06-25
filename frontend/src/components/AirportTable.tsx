// Airport table with expandable rows showing AviationStack enrichment data.
// Click a row to expand/collapse the enrichment details panel.
import { useState } from 'react';
import type { Airport } from '../utils/api';

interface AirportTableProps {
  airports: Airport[];
  onRowClick?: (airport: Airport) => void;
}

export const AirportTable = ({ airports, onRowClick }: AirportTableProps) => {
  // Track which airport row is expanded (by IATA code)
  const [expandedIata, setExpandedIata] = useState<string | null>(null);

  const toggleExpand = (iata: string) => {
    setExpandedIata((prev) => (prev === iata ? null : iata));
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="airport-table">
        <thead>
          <tr className="border-b border-slate-700 text-xs text-slate-400 uppercase tracking-wider">
            <th className="px-4 py-3 text-left w-6"></th>
            <th className="px-4 py-3 text-left">IATA</th>
            <th className="px-4 py-3 text-left">Name</th>
            <th className="px-4 py-3 text-left">City</th>
            <th className="px-4 py-3 text-left">Country</th>
          </tr>
        </thead>
        <tbody>
          {airports.map((airport) => {
            const isExpanded = expandedIata === airport.iata_code;
            const hasEnrichment = !!airport.enriched_at;

            return (
              <tr key={airport.iata_code} className="group">
                {/* Main row — always visible */}
                <td colSpan={5} className="p-0">
                  <div
                    data-testid={`airport-row-${airport.iata_code}`}
                    onClick={() => {
                      toggleExpand(airport.iata_code);
                      onRowClick?.(airport);
                    }}
                    className="flex items-center border-b border-slate-700/50 cursor-pointer hover:bg-surface-hover transition"
                  >
                    {/* Expand indicator */}
                    <span className="px-4 py-3 text-xs text-slate-500 w-6">
                      {hasEnrichment ? (isExpanded ? '▾' : '▸') : ''}
                    </span>
                    <span className="px-4 py-3 font-mono font-medium text-accent w-20">{airport.iata_code}</span>
                    <span className="px-4 py-3 text-slate-200 flex-1">{airport.name}</span>
                    <span className="px-4 py-3 text-slate-300 w-40">{airport.city}</span>
                    <span className="px-4 py-3 text-slate-400 w-40">{airport.country || '—'}</span>
                  </div>

                  {/* Expandable enrichment panel */}
                  {isExpanded && hasEnrichment && (
                    <div
                      data-testid={`airport-enrichment-${airport.iata_code}`}
                      className="px-14 py-3 bg-slate-800/50 border-b border-slate-700/50 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs"
                    >
                      <EnrichmentField label="Timezone" value={airport.timezone} />
                      <EnrichmentField label="GMT Offset" value={airport.gmt ? `UTC${Number(airport.gmt) >= 0 ? '+' : ''}${airport.gmt}` : undefined} />
                      <EnrichmentField label="Country" value={airport.country_name} extra={airport.country_iso2 ? `(${airport.country_iso2})` : undefined} />
                      <EnrichmentField label="City IATA" value={airport.city_iata_code} />
                      <EnrichmentField label="Latitude" value={airport.latitude} />
                      <EnrichmentField label="Longitude" value={airport.longitude} />
                      <EnrichmentField label="Phone" value={airport.phone_number} />
                      <EnrichmentField label="GeoName ID" value={airport.geoname_id} />
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {airports.length === 0 && (
        <div className="text-center py-12 text-slate-500">No airports found</div>
      )}
    </div>
  );
};

/** Small helper component for a single enrichment field label + value. */
const EnrichmentField = ({ label, value, extra }: { label: string; value?: string | null; extra?: string }) => (
  <div>
    <span className="text-slate-500">{label}: </span>
    <span className="text-slate-300">{value || '—'} {extra || ''}</span>
  </div>
);

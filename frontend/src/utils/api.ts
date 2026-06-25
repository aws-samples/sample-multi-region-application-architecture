// API utility functions — attaches Cognito JWT to all requests.
const API_BASE = '/api';
const FLIGHTS_API_BASE = import.meta.env.VITE_FLIGHTS_API_URL || '/api';

// Auth header helper — reads access token from CognitoService.
// Imported dynamically to avoid circular dependency with AuthContext.
async function authHeaders(): Promise<Record<string, string>> {
  const { cognito } = await import('./cognito');
  const token = await cognito.getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Wrapper around fetch that attaches auth headers and handles 401.
async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = { ...init?.headers, ...(await authHeaders()) };
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401) {
    // Token expired or invalid — force logout by reloading to /login
    const { cognito } = await import('./cognito');
    cognito.signOut();
    window.location.href = '/login';
    throw new Error('Session expired');
  }
  return res;
}

export interface RegionInfo {
  region: string;
  role: 'primary' | 'passive';
  taskCount: number;
  status: 'healthy' | 'unhealthy';
}

export interface Airport {
  iata_code: string;
  name: string;
  city: string;
  country?: string;
  timezone?: string;
  country_name?: string;
  country_iso2?: string;
  latitude?: string;
  longitude?: string;
  gmt?: string;
  phone_number?: string;
  geoname_id?: string;
  city_iata_code?: string;
  enriched_at?: string;
}

export interface Stats {
  totalAirports: number;
  connected: boolean;
  lastUpdated: string;
}

export interface Flight {
  flight_number: string;
  airline: string;
  airline_code: string;
  origin_iata: string;
  destination_iata: string;
  origin_city: string;
  destination_city: string;
  departure_time: string;
  arrival_time: string;
  gate: string;
  terminal: string;
  aircraft_type: string;
  status: 'scheduled' | 'boarding' | 'departed' | 'arrived' | 'delayed' | 'cancelled';
}

export interface FlightStats {
  total: number;
  by_status: Record<string, number>;
  busiest_airports: { iata: string; flight_count: number }[];
}

export interface FlightFiltersState {
  airport: string;
  status: string;
  window: '2h' | '6h' | '24h';
}

export const api = {
  async getRegionInfo(): Promise<RegionInfo> {
    const res = await authFetch(`${API_BASE}/region-info`);
    if (!res.ok) throw new Error('Failed to fetch region info');
    return res.json();
  },

  async getAirports(limit = 100): Promise<Airport[]> {
    const res = await authFetch(`${API_BASE}/airports?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch airports');
    const data = await res.json();
    return data.airports || [];
  },

  async getAirport(iata: string): Promise<Airport> {
    const res = await authFetch(`${API_BASE}/airports/${iata}`);
    if (!res.ok) throw new Error('Airport not found');
    return res.json();
  },

  async createAirport(airport: Airport): Promise<{ success: boolean; message: string }> {
    const res = await authFetch(`${API_BASE}/airports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(airport),
    });
    if (!res.ok) throw new Error('Failed to create airport');
    return res.json();
  },

  async getStats(): Promise<Stats> {
    const res = await authFetch(`${API_BASE}/stats`);
    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
  },

  async healthCheck(): Promise<{ status: string }> {
    const res = await authFetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Health check failed');
    return res.json();
  },
};

// --- Flights API (separate API Gateway endpoint) ---
export const flightsApi = {
  async getFlights(filters?: Partial<FlightFiltersState>, limit = 50): Promise<{ flights: Flight[]; count: number; fetched_at?: string }> {
    const params = new URLSearchParams();
    if (filters?.airport) params.set('airport', filters.airport);
    if (filters?.status) params.set('status', filters.status);
    if (filters?.window) params.set('window', filters.window);
    params.set('limit', String(limit));
    const res = await authFetch(`${FLIGHTS_API_BASE}/flights?${params}`);
    if (!res.ok) throw new Error('Failed to fetch flights');
    return res.json();
  },

  async getFlightStats(): Promise<FlightStats> {
    const res = await authFetch(`${FLIGHTS_API_BASE}/flights/stats`);
    if (!res.ok) throw new Error('Failed to fetch flight stats');
    return res.json();
  },

  async seedFlights(count = 300): Promise<{ seeded: number; message: string }> {
    const res = await authFetch(`${FLIGHTS_API_BASE}/flights/seed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count }),
    });
    if (!res.ok) throw new Error('Failed to seed flights');
    return res.json();
  },

  async refreshFlights(): Promise<{ airports_processed: number; flights_fetched: number; cost_estimate: string; fetched_at: string; errors: string[] }> {
    const res = await authFetch(`${FLIGHTS_API_BASE}/flights/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) throw new Error('Failed to refresh flights');
    return res.json();
  },
};

// --- Crew API (Lambda behind ALB at /crew/*) ---

export interface Pilot {
  employee_id: string;
  first_name: string;
  last_name: string;
  designation: 'Captain' | 'First Officer' | 'Second Officer';
  license_number: string;
  date_of_hire: string;
  base_airport: string;
  email: string;
  phone: string;
  qualifications: {
    type_ratings: string[];
    medical_certificate: { status: string; expiry_date: string };
    total_flight_hours: number;
    recent_90_day_hours: number;
  };
  fatigue: { fatigue_risk_score: number; compliance_status: 'GREEN' | 'YELLOW' | 'RED' };
}

export interface FlightAttendant {
  employee_id: string;
  first_name: string;
  last_name: string;
  designation: 'Lead FA' | 'Senior FA' | 'FA';
  certification_level: string;
  date_of_hire: string;
  base_airport: string;
  languages: string[];
  fatigue: { fatigue_risk_score: number; compliance_status: 'GREEN' | 'YELLOW' | 'RED' };
}

export interface Aircraft {
  aircraft_type: string;
  category: string;
  seat_capacity: number;
  required_pilots: number;
  required_fas: number;
  max_range_hours: number;
}

export interface CrewAssignment {
  flight_number: string;
  flight_date: string;
  aircraft_type: string;
  assigned_pilots: { employee_id: string; role: string; compliance_status: string }[];
  assigned_fas: { employee_id: string; role: string; compliance_status: string }[];
  relief_crew: boolean;
  total_crew: number;
}

const CREW_API_BASE = '/api';

export const crewApi = {
  async getPilots(filters?: { base_airport?: string; designation?: string }, limit = 50): Promise<{ items: Pilot[]; count: number; total_count?: number }> {
    const params = new URLSearchParams();
    if (filters?.base_airport) params.set('base_airport', filters.base_airport);
    if (filters?.designation) params.set('designation', filters.designation);
    params.set('limit', String(limit));
    const res = await authFetch(`${CREW_API_BASE}/crew/pilots?${params}`);
    if (!res.ok) throw new Error('Failed to fetch pilots');
    return res.json();
  },

  async getFlightAttendants(filters?: { base_airport?: string; designation?: string }, limit = 50): Promise<{ items: FlightAttendant[]; count: number; total_count?: number }> {
    const params = new URLSearchParams();
    if (filters?.base_airport) params.set('base_airport', filters.base_airport);
    if (filters?.designation) params.set('designation', filters.designation);
    params.set('limit', String(limit));
    const res = await authFetch(`${CREW_API_BASE}/crew/flight-attendants?${params}`);
    if (!res.ok) throw new Error('Failed to fetch flight attendants');
    return res.json();
  },

  async getAircraft(): Promise<{ items: Aircraft[]; count: number }> {
    const res = await authFetch(`${CREW_API_BASE}/crew/aircraft`);
    if (!res.ok) throw new Error('Failed to fetch aircraft');
    return res.json();
  },

  async getAssignments(filters?: { flight_number?: string }, limit = 50): Promise<{ items: CrewAssignment[]; count: number }> {
    const params = new URLSearchParams();
    if (filters?.flight_number) params.set('flight_number', filters.flight_number);
    params.set('limit', String(limit));
    const res = await authFetch(`${CREW_API_BASE}/crew/assignments?${params}`);
    if (!res.ok) throw new Error('Failed to fetch crew assignments');
    return res.json();
  },
};

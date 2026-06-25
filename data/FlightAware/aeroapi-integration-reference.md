# FlightAware AeroAPI v4 — Integration Reference for AirportHub

## AirportHub Integration Context
- **Runtime**: AWS Lambda (Python 3.12) — NOT Docker/Flask/containers
- **Architecture**: Flights Lambda behind ALB, same pattern as existing airport-service/crew-service
- **Caching**: DocumentDB (not flask_caching/SimpleCache/Redis)
- **Refresh**: EventBridge scheduled rule triggers Lambda hourly to fetch and cache flights
- **Secrets**: AWS Secrets Manager (`airporthub/flightaware/api-key`)
- **Auth on API calls**: `x-apikey` header via `requests.Session`
- **Note**: The aeroapps examples in this KB use Flask+Docker — extract only the AeroAPI call patterns and response handling, ignore the Flask/Docker/container parts

## Overview
- **API Version**: 4.17.1
- **Base URL**: `https://aeroapi.flightaware.com/aeroapi`
- **Auth**: Header `x-apikey: <your-api-key>` (no username needed)
- **Format**: RESTful, JSON responses
- **OpenAPI Spec**: `https://flightaware.com/commercial/aeroapi/resources/aeroapi-openapi.yml`

## Pricing (Per-Query Fees)

| Endpoint | Cost per Result Set |
|----------|-------------------|
| `GET /airports/{id}/flights/departures` | $0.005 |
| `GET /airports/{id}/flights/arrivals` | $0.005 |
| `GET /airports/{id}/flights/scheduled_departures` | $0.005 |
| `GET /airports/{id}/flights/scheduled_arrivals` | $0.005 |
| `GET /airports/{id}/flights` (all 4 combined) | $0.020 |
| `GET /airports/{id}/flights/counts` | $0.100 |
| `GET /airports/{id}` (airport info) | $0.015 |
| `GET /airports/{id}/delays` | $0.010 |
| `GET /airports/{id}/weather/observations` | $0.002 |
| `GET /flights/{ident}` | $0.005 |
| `GET /flights/{id}/position` | $0.010 |
| `GET /flights/{id}/track` | $0.012 |
| `GET /flights/search` | $0.050 |
| `GET /operators/{id}` | $0.015 |

**Result set** = up to 15 records. Use `max_pages` to control cost.

## Tier Limits

| Tier | Monthly Min | Rate Limit | Free Credit |
|------|------------|------------|-------------|
| Personal | $0 | 10 result sets/min | $5/mo ($10 for ADS-B feeders) |
| Standard | $100/mo | 5 result sets/sec | — |
| Premium | $1,000/mo | 100 result sets/sec | — |

## Airport Code Format — CRITICAL
AeroAPI uses **ICAO codes** (e.g., `KJFK`, `KIAH`, `EGLL`), NOT IATA codes.
- AirportHub stores IATA codes (e.g., `JFK`, `IAH`, `LHR`)
- Must map IATA → ICAO before calling AeroAPI
- Use `GET /airports/{id}/canonical` ($0.001) to resolve IATA → ICAO
- US airports: prepend `K` to IATA (e.g., `JFK` → `KJFK`) — works for most but not all

## Key Endpoints for AirportHub

### 1. Airport Departures (recently departed)
```
GET /airports/{id}/flights/departures
```
- Returns flights that have departed, ordered by `actual_off` descending
- Default window: last 24 hours
- Params: `airline`, `type` (Airline/General_Aviation), `start`, `end`, `max_pages`, `cursor`
- Response key: `departures[]`

### 2. Airport Arrivals (recently arrived)
```
GET /airports/{id}/flights/arrivals
```
- Returns flights that have arrived, ordered by `actual_on` descending
- Default window: last 24 hours
- Params: same as departures
- Response key: `arrivals[]`

### 3. Scheduled Departures (future)
```
GET /airports/{id}/flights/scheduled_departures
```
- Returns scheduled/upcoming departures, ordered by `estimated_off` ascending
- Default window: 2 hours ago → 24 hours ahead
- Response key: `scheduled_departures[]`

### 4. Scheduled Arrivals (future)
```
GET /airports/{id}/flights/scheduled_arrivals
```
- Returns expected arrivals (undeparted + en route), ordered by `estimated_on` ascending
- Default window: 48 hours ago → 24 hours ahead
- Response key: `scheduled_arrivals[]`

### 5. All Airport Flights (combined)
```
GET /airports/{id}/flights
```
- Returns all 4 categories in one call: `scheduled_arrivals[]`, `scheduled_departures[]`, `arrivals[]`, `departures[]`
- Costs $0.020/result set (4x individual)

### 6. Flight Counts
```
GET /airports/{id}/flights/counts
```
- Returns: `departed`, `enroute`, `scheduled_arrivals`, `scheduled_departures`
- Does NOT include completed or cancelled flights

## BaseFlight Object (Response Schema)

Every flight in departures/arrivals/scheduled responses is a `BaseFlight`:

```json
{
  "ident": "UAL123",
  "ident_icao": "UAL123",
  "ident_iata": "UA123",
  "fa_flight_id": "UAL123-1234567890-airline-0123",
  "operator": "UAL",
  "operator_icao": "UAL",
  "operator_iata": "UA",
  "flight_number": "123",
  "registration": "N12345",
  "aircraft_type": "B738",
  "status": "Scheduled / En Route / Landed",
  "origin": {
    "code": "KJFK",
    "code_icao": "KJFK",
    "code_iata": "JFK",
    "code_lid": "JFK",
    "name": "John F Kennedy Intl",
    "city": "New York",
    "timezone": "America/New_York"
  },
  "destination": {
    "code": "KLAX",
    "code_icao": "KLAX",
    "code_iata": "LAX",
    "name": "Los Angeles Intl",
    "city": "Los Angeles",
    "timezone": "America/Los_Angeles"
  },
  "gate_origin": "B22",
  "gate_destination": "44",
  "terminal_origin": "7",
  "terminal_destination": "4",
  "baggage_claim": "5",
  "scheduled_out": "2021-12-31T19:59:59Z",
  "estimated_out": "2021-12-31T20:05:00Z",
  "actual_out": "2021-12-31T20:03:00Z",
  "scheduled_off": "2021-12-31T20:15:00Z",
  "estimated_off": null,
  "actual_off": "2021-12-31T20:18:00Z",
  "scheduled_on": "2021-12-31T23:30:00Z",
  "estimated_on": "2021-12-31T23:25:00Z",
  "actual_on": null,
  "scheduled_in": "2021-12-31T23:45:00Z",
  "estimated_in": "2021-12-31T23:40:00Z",
  "actual_in": null,
  "departure_delay": 240,
  "arrival_delay": null,
  "filed_ete": 18000,
  "progress_percent": 45,
  "route_distance": 2475,
  "filed_airspeed": 460,
  "filed_altitude": 370,
  "route": "DEEZZ5 DEEZZ DCT BETTE ...",
  "blocked": false,
  "diverted": false,
  "cancelled": false,
  "position_only": false,
  "codeshares": ["AAL8327"],
  "codeshares_iata": ["AA8327"],
  "type": "Airline",
  "seats_cabin_first": 16,
  "seats_cabin_business": 54,
  "seats_cabin_coach": 110
}
```

### OOOI Times Explained
AeroAPI uses the aviation "OOOI" model (Out-Off-On-In):
- **Out** = gate departure (pushback)
- **Off** = runway departure (wheels up)
- **On** = runway arrival (touchdown)
- **In** = gate arrival (at gate)

Each has `scheduled_`, `estimated_`, and `actual_` variants (12 time fields total).

### Status Field
The `status` field is a human-readable string, NOT an enum. Examples:
- "Scheduled"
- "En Route / On Time"
- "En Route / Delayed"
- "Landed / Taxiing"
- "Arrived / Gate Arrival"
- "Cancelled"
- "Diverted"
- "Result Unknown"

Use the `cancelled` and `diverted` boolean flags for programmatic checks.

## AirportHub Field Mapping

Current mock flight fields → AeroAPI mapping:

| AirportHub Field | AeroAPI Source |
|-----------------|---------------|
| `flight_number` | `ident_iata` or `operator_iata + flight_number` |
| `airline` | Look up via `operator_iata` → operator name |
| `airline_code` | `operator_iata` |
| `origin_iata` | `origin.code_iata` |
| `destination_iata` | `destination.code_iata` |
| `origin_city` | `origin.city` |
| `destination_city` | `destination.city` |
| `departure_time` | `scheduled_out` (or `estimated_out` / `actual_out`) |
| `arrival_time` | `scheduled_in` (or `estimated_in` / `actual_in`) |
| `gate` | `gate_origin` (departures) or `gate_destination` (arrivals) |
| `terminal` | `terminal_origin` (departures) or `terminal_destination` (arrivals) |
| `aircraft_type` | `aircraft_type` (ICAO code like "B738", not friendly name) |
| `status` | Derive from `cancelled`, `diverted`, `actual_out/off/on/in`, `progress_percent` |

## Pagination
- `max_pages` (default 1): controls how many result sets (15 records each) to return
- `cursor`: opaque token for next page, returned in `links.next`
- `num_pages`: number of pages actually returned

## Python Integration Example
```python
import requests

API_KEY = "your-api-key"
BASE_URL = "https://aeroapi.flightaware.com/aeroapi"
HEADERS = {"x-apikey": API_KEY}

def get_departures(icao_code: str, max_pages: int = 1) -> list[dict]:
    """Fetch recent departures for an airport."""
    resp = requests.get(
        f"{BASE_URL}/airports/{icao_code}/flights/departures",
        headers=HEADERS,
        params={"max_pages": max_pages, "type": "Airline"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("departures", [])

def get_scheduled_departures(icao_code: str, max_pages: int = 1) -> list[dict]:
    """Fetch upcoming scheduled departures for an airport."""
    resp = requests.get(
        f"{BASE_URL}/airports/{icao_code}/flights/scheduled_departures",
        headers=HEADERS,
        params={"max_pages": max_pages, "type": "Airline"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("scheduled_departures", [])
```

## Cost Estimation for AirportHub

Assuming 20 airports, refreshing every 5 minutes:
- 4 calls per airport per refresh (departures + arrivals + scheduled_dep + scheduled_arr)
- 20 airports × 4 calls × $0.005 = $0.40 per refresh cycle
- 288 cycles/day (every 5 min) × $0.40 = $115.20/day — **too expensive for Personal tier**

**Recommended approach**: Cache in DocumentDB, refresh on-demand or on a longer interval.
- 20 airports × 4 calls × $0.005 = $0.40 per refresh
- Refresh every 30 min = 48 cycles/day × $0.40 = $19.20/day
- Refresh every hour = 24 cycles/day × $0.40 = $9.60/day
- Refresh on-demand (user clicks) = minimal cost

## Error Handling
All errors return:
```json
{
  "title": "Short summary",
  "reason": "Error type name",
  "detail": "Detailed description with remediation",
  "status": 400
}
```
Common HTTP codes: 400 (bad params), 401 (bad API key), 429 (rate limited).

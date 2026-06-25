"""
FlightAware AeroAPI client — fetches live flight data and maps to AirportHub schema.

Used by the Flights Lambda /flights/refresh route to pull real departures/arrivals
from FlightAware and cache them in DocumentDB.

AeroAPI docs: https://flightaware.com/aeroapi/portal/documentation
Auth: x-apikey header (key from Secrets Manager)
Rate limit: Personal tier = 10 result sets/min
"""

import logging
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

AEROAPI_BASE = "https://aeroapi.flightaware.com/aeroapi"

# Maps AeroAPI operator IATA codes to airline names.
# AeroAPI returns operator_iata (e.g., "UA") but not the full name.
# This covers the most common airlines; unknown codes fall back to the code itself.
AIRLINE_NAMES = {
    "AA": "American Airlines", "UA": "United Airlines", "DL": "Delta Air Lines",
    "BA": "British Airways", "LH": "Lufthansa", "AF": "Air France",
    "EK": "Emirates", "SQ": "Singapore Airlines", "QF": "Qantas",
    "AC": "Air Canada", "JL": "Japan Airlines", "NH": "All Nippon Airways",
    "TK": "Turkish Airlines", "LX": "Swiss International", "KL": "KLM Royal Dutch",
    "AS": "Alaska Airlines", "B6": "JetBlue Airways", "WN": "Southwest Airlines",
    "F9": "Frontier Airlines", "NK": "Spirit Airlines", "HA": "Hawaiian Airlines",
    "QR": "Qatar Airways", "EY": "Etihad Airways", "CX": "Cathay Pacific",
    "SU": "Aeroflot", "IB": "Iberia", "AZ": "ITA Airways",
    "SK": "SAS Scandinavian", "TP": "TAP Air Portugal", "LO": "LOT Polish",
}


def _get(api_key: str, path: str, params: dict | None = None) -> dict | None:
    """Make a GET request to AeroAPI. Returns JSON or None on error."""
    try:
        resp = requests.get(
            f"{AEROAPI_BASE}{path}",
            headers={"x-apikey": api_key},
            params=params or {},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("AeroAPI %s returned HTTP %d: %s", path, resp.status_code, resp.text[:200])
        return None
    except Exception as e:
        logger.error("AeroAPI request failed for %s: %s", path, e)
        return None


def derive_status(flight: dict) -> str:
    """
    Derive AirportHub status enum from AeroAPI flight data.

    AeroAPI 'status' is a human-readable string (e.g., "En Route / On Time").
    We map it to our enum: scheduled, boarding, departed, arrived, delayed, cancelled.
    """
    if flight.get("cancelled"):
        return "cancelled"
    if flight.get("diverted"):
        return "delayed"

    # Use the human-readable status string for hints
    status_str = (flight.get("status") or "").lower()

    if "cancel" in status_str:
        return "cancelled"
    if "arrived" in status_str or "landed" in status_str or "taxiing" in status_str:
        return "arrived"
    if "en route" in status_str:
        if "delay" in status_str:
            return "delayed"
        return "departed"

    # Check OOOI times for more precise status
    if flight.get("actual_on") or flight.get("actual_in"):
        return "arrived"
    if flight.get("actual_off") or flight.get("actual_out"):
        return "departed"

    # Check for delays via departure_delay field (seconds)
    dep_delay = flight.get("departure_delay")
    if dep_delay and dep_delay > 900:  # > 15 min delay
        return "delayed"

    if "schedul" in status_str or "filed" in status_str:
        return "scheduled"

    return "scheduled"


def map_flight(fa_flight: dict, direction: str) -> dict:
    """
    Map an AeroAPI BaseFlight object to AirportHub's Flight schema.

    Args:
        fa_flight: Raw flight dict from AeroAPI response
        direction: 'departure' or 'arrival' — determines which gate/terminal to use
    """
    # Extract origin/destination info (nested objects in AeroAPI)
    origin = fa_flight.get("origin") or {}
    destination = fa_flight.get("destination") or {}

    # Build the flight_number — prefer ident_iata, fall back to ident
    flight_number = fa_flight.get("ident_iata") or fa_flight.get("ident") or "Unknown"

    # Airline name from our lookup, fall back to operator code
    airline_code = fa_flight.get("operator_iata") or fa_flight.get("operator") or ""
    airline_name = AIRLINE_NAMES.get(airline_code, airline_code)

    # Pick the best available departure time: actual > estimated > scheduled
    departure_time = (
        fa_flight.get("actual_out")
        or fa_flight.get("estimated_out")
        or fa_flight.get("actual_off")
        or fa_flight.get("estimated_off")
        or fa_flight.get("scheduled_out")
        or fa_flight.get("scheduled_off")
        or ""
    )

    # Pick the best available arrival time
    arrival_time = (
        fa_flight.get("actual_in")
        or fa_flight.get("estimated_in")
        or fa_flight.get("actual_on")
        or fa_flight.get("estimated_on")
        or fa_flight.get("scheduled_in")
        or fa_flight.get("scheduled_on")
        or ""
    )

    # Gate and terminal depend on whether this is a departure or arrival board entry
    if direction == "departure":
        gate = fa_flight.get("gate_origin") or ""
        terminal = fa_flight.get("terminal_origin") or ""
    else:
        gate = fa_flight.get("gate_destination") or ""
        terminal = fa_flight.get("terminal_destination") or ""

    return {
        "flight_number": flight_number,
        "airline": airline_name,
        "airline_code": airline_code,
        "origin_iata": origin.get("code_iata") or origin.get("code") or "",
        "destination_iata": destination.get("code_iata") or destination.get("code") or "",
        "origin_city": origin.get("city") or "",
        "destination_city": destination.get("city") or "",
        "departure_time": departure_time,
        "arrival_time": arrival_time,
        "gate": gate,
        "terminal": terminal,
        "aircraft_type": fa_flight.get("aircraft_type") or "",
        "status": derive_status(fa_flight),
        "source": "flightaware",
        "fa_flight_id": fa_flight.get("fa_flight_id") or "",
        "board_type": direction,
    }


def fetch_airport_flights(icao_code: str, api_key: str) -> list[dict]:
    """
    Fetch all 4 flight categories for an airport from AeroAPI.

    Calls: departures, arrivals, scheduled_departures, scheduled_arrivals
    Cost: 4 × $0.005 = $0.02 per airport (1 page each, up to 15 flights)

    Returns a list of mapped flight dicts ready for DocumentDB insertion.
    """
    flights: list[dict] = []
    params = {"max_pages": 1, "type": "Airline"}

    # Departures (recently departed)
    data = _get(api_key, f"/airports/{icao_code}/flights/departures", params)
    if data:
        for f in data.get("departures", []):
            flights.append(map_flight(f, "departure"))

    # Arrivals (recently arrived)
    data = _get(api_key, f"/airports/{icao_code}/flights/arrivals", params)
    if data:
        for f in data.get("arrivals", []):
            flights.append(map_flight(f, "arrival"))

    # Scheduled departures (upcoming)
    data = _get(api_key, f"/airports/{icao_code}/flights/scheduled_departures", params)
    if data:
        for f in data.get("scheduled_departures", []):
            flights.append(map_flight(f, "departure"))

    # Scheduled arrivals (upcoming)
    data = _get(api_key, f"/airports/{icao_code}/flights/scheduled_arrivals", params)
    if data:
        for f in data.get("scheduled_arrivals", []):
            flights.append(map_flight(f, "arrival"))

    return flights


def refresh_all_airports(airports: list[dict], api_key: str) -> dict:
    """
    Fetch live flights for all airports. Rate-limits to stay under Personal tier limits.

    Args:
        airports: list of airport dicts with 'iata' and 'icao' fields
        api_key: FlightAware AeroAPI key

    Returns:
        dict with airports_processed, flights_fetched, errors, fetched_at
    """
    # Cap at 15 airports per refresh for three reasons:
    #
    # 1. AeroAPI rate limit — Personal tier allows 10 result sets/min.
    #    Each airport needs 4 API calls (departures, arrivals, scheduled_departures,
    #    scheduled_arrivals), so we pace 7 seconds between airports. 15 airports
    #    × 4 calls = 60 calls total, spread across ~105 seconds.
    #
    # 2. ALB idle timeout — the default Application Load Balancer idle timeout is
    #    60 seconds. If the Lambda behind the ALB takes longer than that to respond,
    #    the ALB drops the connection. 15 airports keeps us near that boundary.
    #
    # 3. Cost control — each airport costs ~$0.02 (4 calls × $0.005/call).
    #    15 airports = ~$0.30 per refresh. Keeping this bounded avoids surprise
    #    bills on the Personal tier.
    MAX_AIRPORTS = 15
    airports = airports[:MAX_AIRPORTS]

    all_flights: list[dict] = []
    errors: list[str] = []
    now = datetime.now(timezone.utc).isoformat()
    consecutive_rate_limited = 0  # Track consecutive airports returning 0 flights due to 429

    for i, airport in enumerate(airports):
        icao = airport.get("icao")
        iata = airport.get("iata", "???")
        if not icao:
            errors.append(f"{iata}: missing ICAO code")
            continue

        logger.info("Fetching flights for %s (%s) [%d/%d]", iata, icao, i + 1, len(airports))
        try:
            flights = fetch_airport_flights(icao, api_key)
            # Tag each flight with fetch timestamp
            for f in flights:
                f["fetched_at"] = now
            all_flights.extend(flights)
            logger.info("  Got %d flights for %s", len(flights), iata)

            # Track consecutive rate-limited airports (0 flights = likely 429)
            if len(flights) == 0:
                consecutive_rate_limited += 1
            else:
                consecutive_rate_limited = 0

            # Early exit: stop after 3 consecutive airports return 0 flights
            # This means the API quota is exhausted — no point waiting 7s × remaining airports
            if consecutive_rate_limited >= 3:
                logger.warning("3 consecutive airports returned 0 flights (rate limited) — stopping early")
                break

        except Exception as e:
            logger.error("  Error fetching %s: %s", iata, e)
            errors.append(f"{iata}: {str(e)}")

        # Rate limit: only sleep if we actually got data (not rate-limited)
        # Sleeping when rate-limited wastes time during failover for no benefit
        if i < len(airports) - 1 and consecutive_rate_limited == 0:
            time.sleep(7)  # nosemgrep: arbitrary-sleep
    seen: set[str] = set()
    unique_flights: list[dict] = []
    for f in all_flights:
        fid = f.get("fa_flight_id", "")
        if fid and fid in seen:
            continue
        if fid:
            seen.add(fid)
        unique_flights.append(f)

    return {
        "airports_processed": len(airports) - len(errors),
        "flights_fetched": len(unique_flights),
        "flights": unique_flights,
        "errors": errors,
        "fetched_at": now,
        "cost_estimate": f"~${len(airports) * 0.02:.2f}",
    }

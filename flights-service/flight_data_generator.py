#!/usr/bin/env python3

"""
Flight Data Generator — generates mock flight records and provides
time-relative shifting so stored data always appears as a live 24-hour window.
"""

import random
import hashlib
from datetime import datetime, timedelta, timezone

AIRLINES = [
    ("AA", "American Airlines"),
    ("UA", "United Airlines"),
    ("DL", "Delta Air Lines"),
    ("BA", "British Airways"),
    ("LH", "Lufthansa"),
    ("AF", "Air France"),
    ("EK", "Emirates"),
    ("SQ", "Singapore Airlines"),
    ("QF", "Qantas"),
    ("AC", "Air Canada"),
    ("JL", "Japan Airlines"),
    ("NH", "All Nippon Airways"),
    ("TK", "Turkish Airlines"),
    ("LX", "Swiss International"),
    ("KL", "KLM Royal Dutch"),
]

AIRCRAFT_TYPES = [
    "Boeing 737-800",
    "Boeing 777-300ER",
    "Boeing 787-9",
    "Airbus A320neo",
    "Airbus A330-300",
    "Airbus A350-900",
    "Airbus A380-800",
    "Embraer E190",
    "Boeing 767-300ER",
    "Boeing 747-400",
]

GATE_LETTERS = ["A", "B", "C", "D", "E", "F"]


def _deterministic_delay(flight_number):
    """Return a deterministic delay (30-90 min) based on flight number hash."""
    h = int(hashlib.md5(flight_number.encode(), usedforsecurity=False).hexdigest(), 16)
    return 30 + (h % 61)  # 30 to 90 minutes


def generate_flights(airports, count=300):
    """
    Generate mock flight records.

    Args:
        airports: list of dicts with at least 'iata' and 'city' keys
        count: number of flights to generate (default 300)

    Returns:
        list of flight dicts ready for DocumentDB insertion
    """
    if len(airports) < 2:
        raise ValueError("Need at least 2 airports to generate flights")

    random.seed(42)  # reproducible generation
    flights = []
    used_numbers = set()

    for _ in range(count):
        origin, destination = random.sample(airports, 2)
        airline_code, airline_name = random.choice(AIRLINES)

        # unique flight number
        while True:
            num = random.randint(100, 9999)
            fn = f"{airline_code}{num}"
            if fn not in used_numbers:
                used_numbers.add(fn)
                break

        # offset in the 24h window (0-1440 minutes)
        base_departure_offset = random.randint(0, 1440)

        # flight duration: 60-840 min
        duration = random.randint(60, 840)
        base_arrival_offset = (base_departure_offset + duration) % 1441

        gate = f"{random.choice(GATE_LETTERS)}{random.randint(1, 30)}"
        terminal = str(random.randint(1, 8))
        aircraft = random.choice(AIRCRAFT_TYPES)

        # status distribution: 85% scheduled, 8% delayed, 5% cancelled, 2% random
        roll = random.random()
        if roll < 0.85:
            base_status = "scheduled"
        elif roll < 0.93:
            base_status = "delayed"
        elif roll < 0.98:
            base_status = "cancelled"
        else:
            base_status = random.choice(["scheduled", "delayed"])

        flights.append({
            "flight_number": fn,
            "airline": airline_name,
            "airline_code": airline_code,
            "origin_iata": origin["iata"],
            "destination_iata": destination["iata"],
            "origin_city": origin.get("city", ""),
            "destination_city": destination.get("city", ""),
            "base_departure_offset_minutes": base_departure_offset,
            "base_arrival_offset_minutes": base_arrival_offset,
            "gate": gate,
            "terminal": terminal,
            "aircraft_type": aircraft,
            "base_status": base_status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return flights


def compute_status(departure_time, arrival_time, now, base_status):
    """
    Derive flight status from time position and base status.

    Returns one of: scheduled, boarding, departed, arrived, delayed, cancelled
    """
    if base_status == "cancelled":
        return "cancelled"

    time_to_departure = (departure_time - now).total_seconds() / 60
    flight_duration = (arrival_time - departure_time).total_seconds() / 60
    time_since_departure = (now - departure_time).total_seconds() / 60

    if base_status == "delayed":
        # still show as delayed until it would have departed with the delay
        if time_to_departure > 0:
            return "delayed"
        if time_since_departure < flight_duration:
            return "departed"
        return "arrived"

    # normal status derivation
    if time_to_departure > 60:
        return "scheduled"
    if time_to_departure > 0:
        return "boarding"
    if time_since_departure < flight_duration:
        return "departed"
    return "arrived"


def get_time_shifted_flights(flights, now=None):
    """
    Shift stored base offsets to real timestamps relative to current time.

    The 24h window is centered on `now`:
      reference = now - 12 hours
      departure = reference + offset minutes
      arrival   = reference + arrival offset minutes

    Args:
        flights: list of flight dicts from DocumentDB
        now: datetime (defaults to utcnow)

    Returns:
        list of flight dicts with added departure_time, arrival_time, status fields
    """
    if now is None:
        now = datetime.now(timezone.utc)

    reference = now - timedelta(hours=12)
    shifted = []

    for f in flights:
        dep_offset = f.get("base_departure_offset_minutes", 0)
        arr_offset = f.get("base_arrival_offset_minutes", 0)
        base_status = f.get("base_status", "scheduled")

        departure_time = reference + timedelta(minutes=dep_offset)
        arrival_time = reference + timedelta(minutes=arr_offset)

        # handle wrap-around: if arrival offset < departure offset, add 24h
        if arr_offset < dep_offset:
            arrival_time += timedelta(hours=24)

        # apply deterministic delay for delayed flights
        if base_status == "delayed":
            delay = _deterministic_delay(f.get("flight_number", ""))
            departure_time += timedelta(minutes=delay)
            arrival_time += timedelta(minutes=delay)

        status = compute_status(departure_time, arrival_time, now, base_status)

        result = {
            **{k: v for k, v in f.items() if k != "_id"},
            "departure_time": departure_time.isoformat(),
            "arrival_time": arrival_time.isoformat(),
            "status": status,
        }
        shifted.append(result)

    return shifted

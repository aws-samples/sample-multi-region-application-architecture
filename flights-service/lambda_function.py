#!/usr/bin/env python3

"""
AirportHub Flights Lambda — serves flight data API with time-relative shifting.
Routes: GET /api/flights, GET /api/flights/stats, POST /api/flights/seed, GET /api/flights/health
"""

import os
import json
import logging
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

import boto3
from botocore.exceptions import ClientError
from pymongo import MongoClient
from flight_data_generator import generate_flights
from flightaware_client import refresh_all_airports
from auth import validate_request

# Structured JSON logging — emits {"timestamp", "level", "message", ...} for CloudWatch Insights
class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for CloudWatch Logs Insights queries."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "function_name": "flights-service",
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# Replace default handler with JSON formatter
if logger.handlers:
    logger.handlers[0].setFormatter(JSONFormatter())
else:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

# Configuration from environment
# DOCDB_ENDPOINT and DOCDB_DATABASE are still env vars (set by CloudFormation)
# Credentials come from Secrets Manager
DOCDB_ENDPOINT = os.environ.get("DOCDB_ENDPOINT", "")
DOCDB_PORT = int(os.environ.get("DOCDB_PORT", "27017"))
DOCDB_DATABASE = os.environ.get("DOCDB_DATABASE", "airports")
DOCDB_SECRET_ARN = os.environ.get("DOCDB_SECRET_ARN", "")
FA_SECRET_ARN = os.environ.get("FA_SECRET_ARN", "")

# Connection reuse across warm invocations
_client = None
_db = None
_cached_secret = None
_cached_fa_secret = None


def _get_secret():
    """Retrieve DocumentDB credentials from Secrets Manager (cached across invocations).

    Uses boto3 to call Secrets Manager and parse the JSON secret value.
    The secret contains 'username' and 'password' keys.
    Result is cached in module-level _cached_secret for Lambda warm starts.
    """
    global _cached_secret
    if _cached_secret is not None:
        return _cached_secret

    # boto3 client for Secrets Manager — reads the secret by ARN
    sm_client = boto3.client("secretsmanager")
    try:
        response = sm_client.get_secret_value(SecretId=DOCDB_SECRET_ARN)
        _cached_secret = json.loads(response["SecretString"])
        logger.info("Retrieved DocumentDB credentials from Secrets Manager")
        return _cached_secret
    except ClientError as e:
        logger.error("Failed to retrieve secret %s: %s", DOCDB_SECRET_ARN, e)
        raise


def get_db():
    """Get or create DocumentDB connection (reused across invocations).

    Retrieves credentials from Secrets Manager on first call,
    then caches the pymongo client for subsequent warm invocations.
    """
    global _client, _db
    if _db is not None:
        return _db

    # Get credentials from Secrets Manager instead of env vars
    secret = _get_secret()
    username = quote_plus(secret["username"])
    password = quote_plus(secret["password"])

    conn = (
        f"mongodb://{username}:{password}@{DOCDB_ENDPOINT}:{DOCDB_PORT}/"
        f"?tls=true&tlsCAFile=/var/task/global-bundle.pem"
        f"&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"
    )
    _client = MongoClient(conn, serverSelectionTimeoutMS=10000, retryReads=True)
    _db = _client[DOCDB_DATABASE]
    logger.info("Connected to DocumentDB at %s", DOCDB_ENDPOINT)
    return _db


def _reset_connection():
    """Clear cached connection so next invocation creates a fresh one."""
    global _client, _db
    _client = None
    _db = None


def _get_fa_key() -> str:
    """Retrieve FlightAware API key from Secrets Manager (cached across invocations).

    Requires FA_SECRET_ARN environment variable to be set. The secret must contain
    a JSON object with an 'api_key' field.
    """
    global _cached_fa_secret
    if _cached_fa_secret is not None:
        return _cached_fa_secret

    if not FA_SECRET_ARN:
        raise ValueError("FA_SECRET_ARN environment variable is not configured")

    sm_client = boto3.client("secretsmanager")
    try:
        response = sm_client.get_secret_value(SecretId=FA_SECRET_ARN)
        secret = json.loads(response["SecretString"])
        _cached_fa_secret = secret["api_key"]
        logger.info("Retrieved FlightAware API key from Secrets Manager")
        return _cached_fa_secret
    except ClientError as e:
        logger.error("Failed to retrieve FA secret %s: %s", FA_SECRET_ARN, e)
        raise


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "statusDescription": f"{status_code} OK" if status_code == 200 else f"{status_code} Error",
        "isBase64Encoded": False,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, default=str),
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def get_flights(event):
    """GET /flights — list flights with optional filters."""
    params = event.get("queryStringParameters") or {}
    airport = (params.get("airport") or "").upper()
    status_filter = (params.get("status") or "").lower()
    limit = min(int(params.get("limit", "50")), 300)

    db = get_db()
    query = {}
    if airport:
        query["$or"] = [{"origin_iata": airport}, {"destination_iata": airport}]
    if status_filter:
        query["status"] = status_filter

    # Read flights — only return docs that have real timestamps (source: flightaware)
    # Old mock data without departure_time is excluded
    if "source" not in query:
        query["departure_time"] = {"$exists": True}
    flights = list(db.flights.find(query, {"_id": 0}).sort("departure_time", 1).limit(limit))
    now = datetime.now(timezone.utc)

    # Get the fetched_at timestamp from the most recent flight (data freshness indicator)
    fetched_at = None
    if flights:
        fetched_at = flights[0].get("fetched_at")

    return _response(200, {
        "flights": flights,
        "count": len(flights),
        "fetched_at": fetched_at,
        "timestamp": now.isoformat(),
    })


def get_flight_stats(event):
    """GET /flights/stats — aggregate flight statistics."""
    db = get_db()
    raw = list(db.flights.find())
    now = datetime.now(timezone.utc)
    shifted = get_time_shifted_flights(raw, now)

    by_status = {}
    airport_counts = {}
    for f in shifted:
        s = f["status"]
        by_status[s] = by_status.get(s, 0) + 1
        for key in ("origin_iata", "destination_iata"):
            code = f[key]
            airport_counts[code] = airport_counts.get(code, 0) + 1

    busiest = sorted(airport_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return _response(200, {
        "total": len(shifted),
        "by_status": by_status,
        "busiest_airports": [{"iata": k, "flight_count": v} for k, v in busiest],
        "timestamp": now.isoformat(),
    })


def refresh_flights(event):
    """POST /flights/refresh — fetch live flight data from FlightAware AeroAPI.

    Reads all airports from DocumentDB (needs 'icao' field from enrichment),
    calls AeroAPI for each airport, maps responses, and replaces the flights collection.
    ⚠️ This costs FlightAware API credits (~$0.02 per airport).

    Includes retry logic for DocDB connections after ARC failover — the writer
    endpoint may take 10-30s to become available after a switchover.
    """
    # Retry DocDB connection up to 3 times with 10s backoff
    # After ARC switchover, the new primary writer endpoint needs time to propagate
    db = None
    for attempt in range(3):
        try:
            _reset_connection()  # Force fresh connection each attempt
            db = get_db()
            db.airports.find_one()  # Test the connection actually works
            break
        except Exception as e:
            logger.warning("DocDB connection attempt %d/3 failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(10)  # nosemgrep: arbitrary-sleep

    api_key = _get_fa_key()

    # Get airports with ICAO codes (seed data uses iata_code/icao_code fields)
    raw = list(db.airports.find({"icao_code": {"$exists": True}}, {"_id": 0, "iata_code": 1, "icao_code": 1}))
    airports = [{"iata": a["iata_code"], "icao": a["icao_code"]} for a in raw]
    if not airports:
        return _response(400, {"error": "No airports with ICAO codes. Run enrich_icao.py first."})

    logger.info("Refreshing flights for %d airports from FlightAware", len(airports))
    result = refresh_all_airports(airports, api_key)

    flights = result.pop("flights")
    if flights:
        # Replace existing flights with fresh data
        db.flights.drop()
        db.flights.insert_many(flights)
        db.flights.create_index("origin_iata")
        db.flights.create_index("destination_iata")
        db.flights.create_index("status")
    elif db.flights.count_documents({}) > 0:
        # Rate limited but we have existing data — keep it
        existing = db.flights.count_documents({})
        result["flights_fetched"] = existing
        result["message"] = f"API quota reached — keeping {existing} existing flights"

    logger.info("Refreshed: %d flights from %d airports", result["flights_fetched"], result["airports_processed"])
    return _response(200, result)


def seed_flights(event):
    """POST /flights/seed — generate and store mock flight data (fallback)."""
    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except (json.JSONDecodeError, TypeError):
            pass

    count = int(body.get("count", 300))
    count = max(1, min(count, 1000))

    db = get_db()

    # read airport IATA codes from airports collection
    airports = list(db.airports.find({}, {"_id": 0, "iata": 1, "city": 1}))
    if len(airports) < 2:
        return _response(400, {"error": "Need at least 2 airports in the database. Populate airports first."})

    flights = generate_flights(airports, count)

    # drop and re-insert (idempotent)
    db.flights.drop()
    db.flights.insert_many(flights)
    db.flights.create_index("origin_iata")
    db.flights.create_index("destination_iata")

    logger.info("Seeded %d flights", count)
    return _response(200, {"seeded": count, "message": f"Successfully seeded {count} flights."})


def health_check(event):
    """GET /health — verify DocumentDB connectivity."""
    try:
        db = get_db()
        db.client.admin.command("ping")
        return _response(200, {
            "status": "healthy",
            "region": os.environ.get("AWS_REGION", "unknown"),
            "db_name": DOCDB_DATABASE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return _response(503, {
            "status": "unhealthy",
            "region": os.environ.get("AWS_REGION", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

ROUTES = {
    ("GET", "/api/flights"): get_flights,
    ("GET", "/api/flights/stats"): get_flight_stats,
    ("POST", "/api/flights/seed"): seed_flights,
    ("POST", "/api/flights/refresh"): refresh_flights,
    ("GET", "/api/flights/health"): health_check,
}


def lambda_handler(event, context):
    """Main Lambda entry point — routes requests to handlers.

    Supports three invocation modes:
    1. ALB: top-level httpMethod/path
    2. API Gateway: requestContext.http.method/path
    3. ARC Region Switch: direct invoke with no httpMethod — triggers /flights/refresh
    """
    # ARC direct invocation — no httpMethod means this is an ARC CustomActionLambda call
    # Runs /flights/refresh to seed live FlightAware data during failover
    if not event.get("httpMethod") and not event.get("requestContext"):
        logger.info("ARC direct invocation detected — running /flights/refresh")
        return refresh_flights(event)

    # ALB format: top-level httpMethod and path
    # API Gateway format: requestContext.http.method and requestContext.http.path
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("path") or event.get("requestContext", {}).get("http", {}).get("path", "/")

    # OPTIONS preflight
    if method == "OPTIONS":
        return _response(200, {})

    handler = ROUTES.get((method, path))
    if handler is None:
        return _response(404, {"error": f"Not found: {method} {path}"})

    # Validate JWT for all routes except /health
    if path != "/api/flights/health":
        try:
            validate_request(event)
        except ValueError as e:
            return _response(401, {"error": str(e)})

    try:
        return handler(event)
    except Exception as e:
        logger.exception("Unhandled error in %s %s", method, path)
        _reset_connection()
        return _response(500, {"error": str(e)})

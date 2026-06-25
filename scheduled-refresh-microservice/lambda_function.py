#!/usr/bin/env python3

"""
AirportHub Scheduled Refresh — EventBridge-triggered Lambda that refreshes
flight data from FlightAware AeroAPI into DocumentDB every 24 hours.

Self-contained: uses its own copy of flightaware_client.py, no dependency
on the flights-service Lambda.
"""

import os
import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus

import boto3
from botocore.exceptions import ClientError
from pymongo import MongoClient
from flightaware_client import refresh_all_airports


# --- Structured JSON logging for CloudWatch Insights ---
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "function_name": "scheduled-refresh",
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.handlers:
    logger.handlers[0].setFormatter(JSONFormatter())
else:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

# --- Configuration from environment variables (set by CloudFormation) ---
DOCDB_ENDPOINT = os.environ.get("DOCDB_ENDPOINT", "")
DOCDB_PORT = int(os.environ.get("DOCDB_PORT", "27017"))
DOCDB_DATABASE = os.environ.get("DOCDB_DATABASE", "airports")
DOCDB_SECRET_ARN = os.environ.get("DOCDB_SECRET_ARN", "")
FA_SECRET_ARN = os.environ.get("FA_SECRET_ARN", "")

# --- Cached connections (reused across warm invocations) ---
_client = None
_db = None
_cached_secret = None
_cached_fa_key = None


def _get_secret() -> dict:
    """Retrieve DocumentDB credentials from Secrets Manager (cached)."""
    global _cached_secret
    if _cached_secret is not None:
        return _cached_secret
    sm = boto3.client("secretsmanager")
    resp = sm.get_secret_value(SecretId=DOCDB_SECRET_ARN)
    _cached_secret = json.loads(resp["SecretString"])
    return _cached_secret


def _get_fa_key() -> str:
    """Retrieve FlightAware API key from Secrets Manager (cached)."""
    global _cached_fa_key
    if _cached_fa_key is not None:
        return _cached_fa_key
    sm = boto3.client("secretsmanager")
    resp = sm.get_secret_value(SecretId=FA_SECRET_ARN)
    _cached_fa_key = json.loads(resp["SecretString"])["api_key"]
    return _cached_fa_key


def _get_db():
    """Get or create DocumentDB connection with TLS and retry settings."""
    global _client, _db
    if _db is not None:
        return _db
    secret = _get_secret()
    conn = (
        f"mongodb://{quote_plus(secret['username'])}:{quote_plus(secret['password'])}@{DOCDB_ENDPOINT}:{DOCDB_PORT}/"
        f"?tls=true&tlsCAFile=/var/task/global-bundle.pem"
        f"&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"
    )
    _client = MongoClient(conn, serverSelectionTimeoutMS=10000, retryReads=True)
    _db = _client[DOCDB_DATABASE]
    return _db


def _reset_connection():
    """Clear cached connection for retry."""
    global _client, _db
    _client = None
    _db = None


def lambda_handler(event, context):
    """EventBridge scheduled entry point — refresh flights from FlightAware."""
    region = os.environ.get("AWS_REGION", "unknown")
    logger.info("Scheduled refresh starting in %s", region)

    # Retry DocDB connection up to 3 times with 10s backoff
    import time
    db = None
    for attempt in range(3):
        try:
            _reset_connection()
            db = _get_db()
            db.airports.find_one()  # verify connection works
            break
        except Exception as e:
            logger.warning("DocDB connection attempt %d/3 failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(10)  # nosemgrep: arbitrary-sleep

    # Get airports with ICAO codes (seed data uses iata_code/icao_code fields)
    raw = list(db.airports.find(
        {"icao_code": {"$exists": True}},
        {"_id": 0, "iata_code": 1, "icao_code": 1},
    ))
    airports = [{"iata": a["iata_code"], "icao": a["icao_code"]} for a in raw]
    if not airports:
        logger.error("No airports with ICAO codes found")
        return {"status": "error", "message": "No airports with ICAO codes"}

    logger.info("Refreshing flights for %d airports", len(airports))

    # Fetch live data from FlightAware AeroAPI
    api_key = _get_fa_key()
    result = refresh_all_airports(airports, api_key)
    flights = result.pop("flights")

    if flights:
        # Ensure indexes exist (idempotent — safe to call every run)
        db.flights.create_index(
            [("fa_flight_id", 1), ("board_type", 1)],
            unique=True,
            name="upsert_key",
        )
        db.flights.create_index("origin_iata")
        db.flights.create_index("destination_iata")
        db.flights.create_index("status")

        # Upsert each flight individually — partial API failures won't wipe existing data.
        # replace_one with upsert=True either updates the matching doc or inserts a new one.
        upserted = 0
        updated = 0
        for flight in flights:
            result_op = db.flights.replace_one(
                {"fa_flight_id": flight["fa_flight_id"], "board_type": flight["board_type"]},
                flight,
                upsert=True,
            )
            if result_op.upserted_id:
                upserted += 1
            elif result_op.modified_count:
                updated += 1

        logger.info("Upsert results: %d new, %d updated out of %d flights", upserted, updated, len(flights))

        # Clean up stale flights older than 7 days to prevent indefinite collection growth.
        # Flights no longer returned by the API will linger — this removes them.
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        stale = db.flights.delete_many({"fetched_at": {"$lt": cutoff}})
        if stale.deleted_count:
            logger.info("Cleaned up %d stale flights (older than 7 days)", stale.deleted_count)

    logger.info(
        "Refresh complete: %d flights from %d airports, errors: %s",
        result["flights_fetched"], result["airports_processed"], result.get("errors", []),
    )
    return {
        "status": "success",
        "region": region,
        "flights_fetched": result["flights_fetched"],
        "airports_processed": result["airports_processed"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

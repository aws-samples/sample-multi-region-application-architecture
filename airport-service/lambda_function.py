"""
Airport Lambda handler — CRUD operations for airport data in DocumentDB.
Receives ALB events, validates Cognito JWT, queries DocumentDB.
"""

import os
import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus

import pymongo
from auth import validate_request

# Structured JSON logging — emits {"timestamp", "level", "message", ...} for CloudWatch Insights
class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for CloudWatch Logs Insights queries."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "function_name": "airport-service",
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.handlers:
    logger.handlers[0].setFormatter(JSONFormatter())
else:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

# --- Configuration from environment variables ---
DOCDB_ENDPOINT = os.environ.get("DOCDB_ENDPOINT", "")
DOCDB_PORT = int(os.environ.get("DOCDB_PORT", "27017"))
DOCDB_SECRET_ARN = os.environ.get("DOCDB_SECRET_ARN", "")
DOCDB_DATABASE = os.environ.get("DOCDB_DATABASE", "airports")
DOCDB_COLLECTION = os.environ.get("DOCDB_COLLECTION", "airports")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Module-level connection (reused across warm invocations)
_client = None
_collection = None


def _get_secret() -> dict:
    """Retrieve DocumentDB credentials from Secrets Manager."""
    import boto3
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    resp = client.get_secret_value(SecretId=DOCDB_SECRET_ARN)
    return json.loads(resp["SecretString"])


def _get_collection():
    """Lazy-init DocumentDB connection, reused across warm invocations."""
    global _client, _collection
    if _collection is not None:
        return _collection

    secret = _get_secret()
    uri = (
        f"mongodb://{quote_plus(secret['username'])}:{quote_plus(secret['password'])}@"
        f"{DOCDB_ENDPOINT}:{DOCDB_PORT}/?tls=true&tlsCAFile=global-bundle.pem"
        f"&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"
    )
    _client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=10000, retryReads=True)
    _collection = _client[DOCDB_DATABASE][DOCDB_COLLECTION]
    logger.info("Connected to DocumentDB: %s/%s", DOCDB_DATABASE, DOCDB_COLLECTION)
    return _collection


def _reset_connection():
    """Clear cached connection so next invocation creates a fresh one."""
    global _client, _collection
    _client = None
    _collection = None


def _response(status_code: int, body: dict) -> dict:
    """Build an ALB-compatible response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
        "isBase64Encoded": False,
    }


def _handle_list(event: dict) -> dict:
    """GET /api/airports — list airports with optional ?limit= param."""
    params = event.get("queryStringParameters") or {}
    limit = int(params.get("limit", 50))

    col = _get_collection()
    airports = list(col.find({}, {"_id": 0}).limit(limit))

    return _response(200, {
        "count": len(airports),
        "region": AWS_REGION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "airports": airports,
    })


def _handle_get(iata_code: str) -> dict:
    """GET /api/airports/<iata> — get single airport."""
    col = _get_collection()
    airport = col.find_one({"iata_code": iata_code.upper()}, {"_id": 0})

    if airport:
        return _response(200, {
            "airport": airport,
            "region": AWS_REGION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    return _response(404, {"error": "Airport not found", "iata": iata_code})


def _handle_create(event: dict) -> dict:
    """POST /api/airports — create or update airport."""
    body = json.loads(event.get("body") or "{}")
    if not body or "iata_code" not in body:
        return _response(400, {"error": "IATA code required"})

    body["updated_at"] = datetime.now(timezone.utc).isoformat()
    body["updated_region"] = AWS_REGION

    col = _get_collection()
    result = col.update_one({"iata_code": body["iata_code"]}, {"$set": body}, upsert=True)

    return _response(200, {
        "success": True,
        "iata_code": body["iata_code"],
        "modified": result.modified_count,
        "upserted": result.upserted_id is not None,
        "region": AWS_REGION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def lambda_handler(event: dict, context) -> dict:
    """Main handler — routes ALB events to the appropriate function."""
    # Validate Cognito JWT (skips if COGNITO_USER_POOL_ID is empty)
    try:
        validate_request(event)
    except ValueError as e:
        return _response(401, {"error": str(e)})

    method = event.get("httpMethod", "GET")
    path = event.get("path", "")

    try:
        # Route: GET /api/airports/<iata>
        if method == "GET" and path.startswith("/api/airports/"):
            iata = path.split("/api/airports/")[1].strip("/")
            if iata:
                return _handle_get(iata)

        # Route: GET /api/airports
        if method == "GET" and path.rstrip("/") == "/api/airports":
            return _handle_list(event)

        # Route: POST /api/airports
        if method == "POST" and path.rstrip("/") == "/api/airports":
            return _handle_create(event)

        return _response(404, {"error": "Not found", "path": path})

    except Exception as e:
        logger.error("Airport handler error: %s", e)
        _reset_connection()
        return _response(500, {"error": str(e), "region": AWS_REGION})

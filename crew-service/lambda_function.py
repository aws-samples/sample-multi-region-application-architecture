#!/usr/bin/env python3

"""
AirportHub Crew Service Lambda — CRUD APIs for crew management.
Routes: /api/crew/pilots, /api/crew/flight-attendants, /api/crew/aircraft, /api/crew/assignments, /api/crew/health
"""

import os
import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus

import boto3
from botocore.exceptions import ClientError
from pymongo import MongoClient
from bson import ObjectId
from auth import validate_request

# Structured JSON logging — emits {"timestamp", "level", "message", ...} for CloudWatch Insights
class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for CloudWatch Logs Insights queries."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "function_name": "crew-service",
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

# Configuration from environment
DOCDB_ENDPOINT = os.environ.get("DOCDB_ENDPOINT", "")
DOCDB_PORT = int(os.environ.get("DOCDB_PORT", "27017"))
DOCDB_DATABASE = os.environ.get("DOCDB_DATABASE", "airports")
DOCDB_SECRET_ARN = os.environ.get("DOCDB_SECRET_ARN", "")

# Connection reuse across warm invocations
_client = None
_db = None
_cached_secret = None


def _get_secret():
    """Retrieve DocumentDB credentials from Secrets Manager (cached)."""
    global _cached_secret
    if _cached_secret is not None:
        return _cached_secret
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
    """Get or create DocumentDB connection (reused across warm invocations)."""
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
    logger.info("Connected to DocumentDB at %s", DOCDB_ENDPOINT)
    return _db


def _reset_connection():
    """Clear cached connection so next invocation creates a fresh one."""
    global _client, _db
    _client = None
    _db = None


def _response(status_code: int, body: dict) -> dict:
    """Build ALB-compatible response."""
    return {
        "statusCode": status_code,
        "statusDescription": f"{status_code} OK" if status_code == 200 else f"{status_code} Error",
        "isBase64Encoded": False,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _parse_body(event: dict) -> dict:
    """Parse JSON body from event, return empty dict on failure."""
    if event.get("body"):
        try:
            return json.loads(event["body"])
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


# ---------------------------------------------------------------------------
# Generic CRUD helpers — each collection uses these with its own config
# ---------------------------------------------------------------------------

def _list_documents(collection_name: str, event: dict, id_field: str, filter_fields: list[str]) -> dict:
    """GET — list documents with optional filters."""
    params = event.get("queryStringParameters") or {}
    limit = min(int(params.get("limit", "50")), 1000)
    query = {}
    for field in filter_fields:
        # Convert URL param (kebab-case) to DB field (snake_case)
        param_key = field.replace("_", "-")
        val = params.get(param_key) or params.get(field)
        if val:
            query[field] = val
    db = get_db()
    docs = list(db[collection_name].find(query, {"_id": 0}).limit(limit))
    total = db[collection_name].count_documents(query)
    return _response(200, {"items": docs, "count": len(docs), "total_count": total})


def _get_document(collection_name: str, id_field: str, id_value: str) -> dict:
    """GET — single document by ID field."""
    db = get_db()
    doc = db[collection_name].find_one({id_field: id_value}, {"_id": 0})
    if not doc:
        return _response(404, {"error": f"Not found: {id_value}"})
    return _response(200, doc)


def _create_document(collection_name: str, event: dict) -> dict:
    """POST — insert a new document."""
    body = _parse_body(event)
    if not body:
        return _response(400, {"error": "Request body required"})
    db = get_db()
    db[collection_name].insert_one(body)
    return _response(200, {"message": "Created successfully"})


def _update_document(collection_name: str, id_field: str, id_value: str, event: dict) -> dict:
    """PUT — update an existing document."""
    body = _parse_body(event)
    if not body:
        return _response(400, {"error": "Request body required"})
    db = get_db()
    result = db[collection_name].update_one({id_field: id_value}, {"$set": body})
    if result.matched_count == 0:
        return _response(404, {"error": f"Not found: {id_value}"})
    return _response(200, {"message": "Updated successfully"})


def _delete_document(collection_name: str, id_field: str, id_value: str) -> dict:
    """DELETE — remove a document."""
    db = get_db()
    result = db[collection_name].delete_one({id_field: id_value})
    if result.deleted_count == 0:
        return _response(404, {"error": f"Not found: {id_value}"})
    return _response(200, {"message": "Deleted successfully"})


# ---------------------------------------------------------------------------
# Route handlers — thin wrappers around generic CRUD
# ---------------------------------------------------------------------------

# Pilots
def list_pilots(event):
    return _list_documents("pilots", event, "employee_id", ["base_airport", "designation"])

def get_pilot(event, employee_id):
    return _get_document("pilots", "employee_id", employee_id)

def create_pilot(event):
    return _create_document("pilots", event)

def update_pilot(event, employee_id):
    return _update_document("pilots", "employee_id", employee_id, event)

def delete_pilot(event, employee_id):
    return _delete_document("pilots", "employee_id", employee_id)


# Flight Attendants
def list_flight_attendants(event):
    return _list_documents("flight_attendants", event, "employee_id", ["base_airport", "designation"])

def get_flight_attendant(event, employee_id):
    return _get_document("flight_attendants", "employee_id", employee_id)

def create_flight_attendant(event):
    return _create_document("flight_attendants", event)

def update_flight_attendant(event, employee_id):
    return _update_document("flight_attendants", "employee_id", employee_id, event)

def delete_flight_attendant(event, employee_id):
    return _delete_document("flight_attendants", "employee_id", employee_id)


# Aircraft
def list_aircraft(event):
    return _list_documents("aircraft", event, "aircraft_type", ["category"])

def get_aircraft(event, aircraft_type):
    return _get_document("aircraft", "aircraft_type", aircraft_type)

def create_aircraft(event):
    return _create_document("aircraft", event)

def update_aircraft(event, aircraft_type):
    return _update_document("aircraft", "aircraft_type", aircraft_type, event)

def delete_aircraft(event, aircraft_type):
    return _delete_document("aircraft", "aircraft_type", aircraft_type)


# Crew Assignments
def list_assignments(event):
    return _list_documents("crew_assignments", event, "flight_number", ["flight_number", "flight_date"])

def get_assignment(event, assignment_id):
    """Lookup by ObjectId string or flight_number."""
    db = get_db()
    # Try ObjectId first, fall back to flight_number
    doc = None
    try:
        doc = db.crew_assignments.find_one({"_id": ObjectId(assignment_id)})
    except Exception:
        doc = db.crew_assignments.find_one({"flight_number": assignment_id})
    if not doc:
        return _response(404, {"error": f"Not found: {assignment_id}"})
    doc["_id"] = str(doc["_id"])
    return _response(200, doc)

def create_assignment(event):
    return _create_document("crew_assignments", event)

def update_assignment(event, assignment_id):
    """Update by ObjectId string or flight_number."""
    body = _parse_body(event)
    if not body:
        return _response(400, {"error": "Request body required"})
    db = get_db()
    try:
        result = db.crew_assignments.update_one({"_id": ObjectId(assignment_id)}, {"$set": body})
    except Exception:
        result = db.crew_assignments.update_one({"flight_number": assignment_id}, {"$set": body})
    if result.matched_count == 0:
        return _response(404, {"error": f"Not found: {assignment_id}"})
    return _response(200, {"message": "Updated successfully"})

def delete_assignment(event, assignment_id):
    """Delete by ObjectId string or flight_number."""
    db = get_db()
    try:
        result = db.crew_assignments.delete_one({"_id": ObjectId(assignment_id)})
    except Exception:
        result = db.crew_assignments.delete_one({"flight_number": assignment_id})
    if result.deleted_count == 0:
        return _response(404, {"error": f"Not found: {assignment_id}"})
    return _response(200, {"message": "Deleted successfully"})


# Health
def health_check(event):
    """GET /crew/health — verify DocumentDB connectivity."""
    try:
        db = get_db()
        db.client.admin.command("ping")
        return _response(200, {
            "status": "healthy",
            "service": "crew-service",
            "region": os.environ.get("AWS_REGION", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return _response(503, {"status": "unhealthy", "error": str(e)})


# ---------------------------------------------------------------------------
# Router — matches method + path to handler
# ---------------------------------------------------------------------------

# Static routes (no path params)
STATIC_ROUTES = {
    ("GET", "/api/crew/pilots"): list_pilots,
    ("POST", "/api/crew/pilots"): create_pilot,
    ("GET", "/api/crew/flight-attendants"): list_flight_attendants,
    ("POST", "/api/crew/flight-attendants"): create_flight_attendant,
    ("GET", "/api/crew/aircraft"): list_aircraft,
    ("POST", "/api/crew/aircraft"): create_aircraft,
    ("GET", "/api/crew/assignments"): list_assignments,
    ("POST", "/api/crew/assignments"): create_assignment,
    ("GET", "/api/crew/health"): health_check,
}

# Dynamic route patterns: (method, prefix, handler) — handler receives (event, id_value)
DYNAMIC_ROUTES = [
    ("GET",    "/api/crew/pilots/",             get_pilot),
    ("PUT",    "/api/crew/pilots/",             update_pilot),
    ("DELETE", "/api/crew/pilots/",             delete_pilot),
    ("GET",    "/api/crew/flight-attendants/",  get_flight_attendant),
    ("PUT",    "/api/crew/flight-attendants/",  update_flight_attendant),
    ("DELETE", "/api/crew/flight-attendants/",  delete_flight_attendant),
    ("GET",    "/api/crew/aircraft/",           get_aircraft),
    ("PUT",    "/api/crew/aircraft/",           update_aircraft),
    ("DELETE", "/api/crew/aircraft/",           delete_aircraft),
    ("GET",    "/api/crew/assignments/",        get_assignment),
    ("PUT",    "/api/crew/assignments/",        update_assignment),
    ("DELETE", "/api/crew/assignments/",        delete_assignment),
]


def lambda_handler(event, context):
    """Main entry point — routes requests to handlers."""
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("path") or event.get("requestContext", {}).get("http", {}).get("path", "/")

    if method == "OPTIONS":
        return _response(200, {})

    # Try static routes first
    handler = STATIC_ROUTES.get((method, path))
    if handler:
        if path != "/api/crew/health":
            try:
                validate_request(event)
            except ValueError as e:
                return _response(401, {"error": str(e)})
        try:
            return handler(event)
        except Exception as e:
            logger.exception("Error in %s %s", method, path)
            _reset_connection()
            return _response(500, {"error": str(e)})

    # Try dynamic routes (path params)
    for route_method, prefix, route_handler in DYNAMIC_ROUTES:
        if method == route_method and path.startswith(prefix):
            id_value = path[len(prefix):]
            if id_value:
                try:
                    validate_request(event)
                except ValueError as e:
                    return _response(401, {"error": str(e)})
                try:
                    return route_handler(event, id_value)
                except Exception as e:
                    logger.exception("Error in %s %s", method, path)
                    _reset_connection()
                    return _response(500, {"error": str(e)})

    return _response(404, {"error": f"Not found: {method} {path}"})

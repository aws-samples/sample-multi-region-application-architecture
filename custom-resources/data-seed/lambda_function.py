"""
Data Seed — CloudFormation Custom Resource Lambda.

Seeds airport and crew data into DocumentDB on stack CREATE.
No-op on UPDATE and DELETE. Uses replace_one with upsert for idempotency.
"""

import json
import logging
import os
import urllib.parse
import urllib.request

import boto3
from pymongo import MongoClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def send_cfn_response(event: dict, context, status: str, data: dict = None, reason: str = "") -> None:
    """Send response back to CloudFormation."""
    response_body = json.dumps({
        "Status": status,
        "Reason": reason or f"See CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": event.get("PhysicalResourceId", f"data-seed-{event.get('StackId', 'unknown').split('/')[-1]}"),
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data or {},
    })
    req = urllib.request.Request(
        event["ResponseURL"],
        data=response_body.encode("utf-8"),
        headers={"Content-Type": ""},
        method="PUT",
    )
    urllib.request.urlopen(req)
    logger.info(f"CFN response sent: {status}")


def get_docdb_credentials(secret_arn: str) -> dict:
    """Retrieve DocumentDB credentials from Secrets Manager."""
    sm = boto3.client("secretsmanager")
    response = sm.get_secret_value(SecretId=secret_arn)
    return json.loads(response["SecretString"])


def get_docdb_client(endpoint: str, credentials: dict) -> MongoClient:
    """
    Create a MongoClient connected to DocumentDB with TLS.

    The global-bundle.pem certificate is bundled in the Lambda deployment package
    for TLS verification against DocumentDB's CA.

    urllib.parse.quote_plus escapes special characters in the password
    (e.g., @, /, :) that would break the MongoDB connection string URI format.
    """
    username = urllib.parse.quote_plus(credentials["username"])
    password = urllib.parse.quote_plus(credentials["password"])

    # Build connection string with TLS — DocumentDB requires TLS by default
    connection_string = (
        f"mongodb://{username}:{password}@{endpoint}:27017/"
        f"?tls=true&tlsCAFile=/var/task/global-bundle.pem"
        f"&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"
    )
    return MongoClient(connection_string)


def seed_airports(db) -> int:
    """Seed airport data using replace_one with upsert for idempotency."""
    # Load airport data from bundled JSON file
    data_path = os.path.join(os.path.dirname(__file__), "airports.json")
    with open(data_path, "r") as f:
        airports = json.load(f)

    collection = db["airports"]
    count = 0
    for airport in airports:
        # Use IATA code as the unique key for upsert
        collection.replace_one(
            {"iata_code": airport["iata_code"]},
            airport,
            upsert=True
        )
        count += 1

    logger.info(f"Seeded {count} airports")
    return count


def seed_crew(db) -> int:
    """Seed crew data using replace_one with upsert for idempotency."""
    data_path = os.path.join(os.path.dirname(__file__), "crew.json")
    with open(data_path, "r") as f:
        crew_data = json.load(f)

    for collection_name, records in crew_data.items():
        collection = db[collection_name]
        for record in records:
            # Determine unique key based on collection type
            if "employee_id" in record:
                key_field = "employee_id"
            elif "aircraft_type" in record:
                key_field = "aircraft_type"
            elif "flight_number" in record:
                key_field = "flight_number"
            else:
                key_field = "_id"
            collection.replace_one(
                {key_field: record[key_field]},
                record,
                upsert=True
            )
        logger.info(f"Seeded {len(records)} records into {collection_name}")

    return sum(len(records) for records in crew_data.values())


def handler(event: dict, context) -> None:
    """
    CloudFormation Custom Resource handler.

    ResourceProperties:
        DocDbEndpoint: str — DocumentDB cluster endpoint
        DocDbSecretArn: str — Secrets Manager secret ARN
        DatabaseName: str — database name (default: airports)
    """
    logger.info(f"Event: {json.dumps(event)}")
    request_type = event["RequestType"]

    try:
        if request_type in ("Create", "Update"):
            props = event["ResourceProperties"]
            endpoint = props["DocDbEndpoint"]
            secret_arn = props["DocDbSecretArn"]
            db_name = props.get("DatabaseName", "airports")

            credentials = get_docdb_credentials(secret_arn)
            client = get_docdb_client(endpoint, credentials)
            db = client[db_name]

            airports_count = seed_airports(db)
            crew_count = seed_crew(db)

            client.close()

            send_cfn_response(event, context, "SUCCESS", {
                "AirportsSeeded": str(airports_count),
                "CrewSeeded": str(crew_count),
            })

        elif request_type == "Delete":
            # No-op — data persists, cleanup handled by teardown
            logger.info("Delete — no-op")
            send_cfn_response(event, context, "SUCCESS")

    except Exception as err:
        logger.error(f"Failed: {err}", exc_info=True)
        send_cfn_response(event, context, "FAILED", reason=str(err))

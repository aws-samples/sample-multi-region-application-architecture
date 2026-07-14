#!/usr/bin/env python3

"""
ECS DocumentDB Demo Application
Flask API for DocumentDB operations with pilot light failover support
"""

import os
import json
import logging
from datetime import datetime
from urllib.parse import quote_plus
from urllib.parse import quote_plus
from flask import Flask, jsonify, request, send_from_directory
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import boto3
from botocore.exceptions import ClientError
from auth import require_auth

# Structured JSON logging — emits {"timestamp", "level", "message", ...} for CloudWatch Insights
class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for CloudWatch Logs Insights queries."""
    def format(self, record):
        import json as _json
        from datetime import datetime as _dt, timezone as _tz
        log_entry = {
            "timestamp": _dt.now(_tz.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": "flask-app",
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return _json.dumps(log_entry, default=str)

_json_handler = logging.StreamHandler()
_json_handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_json_handler])
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='')


@app.after_request
def set_cache_headers(response):
    """Set long-lived cache for hashed static assets (JS/CSS with content hash in filename)."""
    if request.path.startswith('/assets/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response

# Configuration
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
SECRET_NAME = os.environ.get('DOCDB_SECRET_NAME', '')
USE_SECRETS_MANAGER = os.environ.get('USE_SECRETS_MANAGER', 'false').lower() == 'true'

# Fallback to environment variables if Secrets Manager not used
DOCDB_ENDPOINT = os.environ.get('DOCDB_ENDPOINT', 'localhost')
DOCDB_PORT = int(os.environ.get('DOCDB_PORT', '27017'))
DOCDB_USERNAME = os.environ.get('DOCDB_USERNAME', 'docdbadmin')
DOCDB_PASSWORD = os.environ.get('DOCDB_PASSWORD', '')
DOCDB_DATABASE = os.environ.get('DOCDB_DATABASE', 'airports')
DOCDB_COLLECTION = os.environ.get('DOCDB_COLLECTION', 'airports')
DOCDB_TLS_ENABLED = os.environ.get('DOCDB_TLS_ENABLED', 'true').lower() == 'true'

# Global MongoDB client
mongo_client = None
db = None
collection = None

def get_secret():
    """Retrieve DocumentDB credentials from AWS Secrets Manager"""
    if not SECRET_NAME:
        logger.warning("SECRET_NAME not set, using environment variables")
        return None
    
    try:
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=AWS_REGION
        )
        
        response = client.get_secret_value(SecretId=SECRET_NAME)
        
        if 'SecretString' in response:
            secret = json.loads(response['SecretString'])
            logger.info(f"Successfully retrieved secret: {SECRET_NAME}")
            return secret
        else:
            logger.error("Secret is binary, expected JSON string")
            return None
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceNotFoundException':
            logger.error(f"Secret {SECRET_NAME} not found")
        elif error_code == 'InvalidRequestException':
            logger.error(f"Invalid request for secret {SECRET_NAME}")
        elif error_code == 'InvalidParameterException':
            logger.error(f"Invalid parameter for secret {SECRET_NAME}")
        elif error_code == 'DecryptionFailure':
            logger.error(f"Cannot decrypt secret {SECRET_NAME}")
        elif error_code == 'InternalServiceError':
            logger.error("Secrets Manager internal error")
        else:
            logger.error(f"Error retrieving secret: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error retrieving secret: {e}")
        return None

def load_credentials():
    """Load DocumentDB credentials from Secrets Manager or environment"""
    global DOCDB_ENDPOINT, DOCDB_PORT, DOCDB_USERNAME, DOCDB_PASSWORD
    
    if USE_SECRETS_MANAGER:
        logger.info("Loading credentials from Secrets Manager")
        secret = get_secret()
        
        if secret:
            DOCDB_ENDPOINT = secret.get('host', DOCDB_ENDPOINT)
            DOCDB_PORT = int(secret.get('port', DOCDB_PORT))
            DOCDB_USERNAME = secret.get('username', DOCDB_USERNAME)
            DOCDB_PASSWORD = secret.get('password', DOCDB_PASSWORD)
            logger.info(f"Credentials loaded from Secrets Manager for {DOCDB_ENDPOINT}")
        else:
            logger.warning("Failed to load from Secrets Manager, using environment variables")
    else:
        logger.info("Using credentials from environment variables")

# Get ECS metadata for task count
def get_ecs_task_count():
    """Get current ECS task count from environment or metadata"""
    try:
        import requests
        metadata_uri = os.environ.get('ECS_CONTAINER_METADATA_URI_V4')
        if metadata_uri:
            response = requests.get(f"{metadata_uri}/task", timeout=1)
            if response.ok:
                # Task is running if we can reach metadata
                return int(os.environ.get('DESIRED_COUNT', 2))
    except Exception:
        pass
    return int(os.environ.get('DESIRED_COUNT', 3))

def init_mongodb():
    """Initialize MongoDB connection"""
    global mongo_client, db, collection
    
    # Load credentials from Secrets Manager or environment
    load_credentials()
    
    try:
        # Build connection string — URL-encode credentials (password may have special chars)
        encoded_user = quote_plus(DOCDB_USERNAME)
        encoded_pass = quote_plus(DOCDB_PASSWORD)
        if DOCDB_TLS_ENABLED:
            connection_string = (
                f"mongodb://{encoded_user}:{encoded_pass}@"
                f"{DOCDB_ENDPOINT}:{DOCDB_PORT}/?tls=true&tlsCAFile=global-bundle.pem"
                f"&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"
            )
        else:
            connection_string = (
                f"mongodb://{encoded_user}:{encoded_pass}@"
                f"{DOCDB_ENDPOINT}:{DOCDB_PORT}/?retryWrites=false"
            )
        
        logger.info(f"Connecting to DocumentDB at {DOCDB_ENDPOINT}:{DOCDB_PORT}")
        logger.info(f"Region: {AWS_REGION}")
        logger.info(f"TLS Enabled: {DOCDB_TLS_ENABLED}")
        
        mongo_client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        
        # Test connection
        mongo_client.admin.command('ping')
        
        db = mongo_client[DOCDB_DATABASE]
        collection = db[DOCDB_COLLECTION]
        
        logger.info(f"Successfully connected to DocumentDB database: {DOCDB_DATABASE}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to connect to DocumentDB: {str(e)}")
        return False

@app.route('/')
def serve_react():
    """Serve React app index"""
    return send_from_directory(app.static_folder, 'index.html')

@app.errorhandler(404)
def fallback_to_react(e):
    """Serve React app for all non-API routes (SPA client-side routing)"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """Runtime config for the frontend — Cognito IDs that vary per deployment"""
    return jsonify({
        'cognitoUserPoolId': os.environ.get('COGNITO_USER_POOL_ID', ''),
        'cognitoClientId': os.environ.get('COGNITO_APP_CLIENT_ID', ''),
        'region': AWS_REGION,
    }), 200

@app.route('/api/region-info', methods=['GET'])
@require_auth
def region_info():
    """Get region and deployment information — no-cache to ensure correct region after failover"""
    try:
        task_count = get_ecs_task_count()
    except Exception:
        task_count = 0
    is_primary = task_count > 0
    
    resp = jsonify({
        'region': AWS_REGION,
        'role': 'primary' if is_primary else 'passive',
        'taskCount': task_count,
        'status': 'healthy' if mongo_client else 'unhealthy'
    })
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp, 200

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for ALB"""
    try:
        if mongo_client is None:
            init_mongodb()
        
        # Ping DocumentDB
        mongo_client.admin.command('ping')
        
        return jsonify({
            'status': 'healthy',
            'region': AWS_REGION,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'region': AWS_REGION,
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@app.route('/api/stats', methods=['GET'])
@require_auth
def get_stats():
    """Get database statistics"""
    try:
        if collection is None:
            init_mongodb()
        
        count = collection.count_documents({})
        
        return jsonify({
            'totalAirports': count,
            'connected': mongo_client is not None,
            'database': DOCDB_DATABASE,
            'collection': DOCDB_COLLECTION,
            'region': AWS_REGION,
            'lastUpdated': datetime.utcnow().isoformat(),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        return jsonify({
            'error': str(e),
            'region': AWS_REGION
        }), 500

if __name__ == '__main__':
    # Initialize MongoDB connection on startup
    init_mongodb()
    
    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

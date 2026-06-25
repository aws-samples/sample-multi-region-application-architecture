# Schedule Toggle Lambda — enables/disables EventBridge schedule rules during ARC failover
# Called by the FlightAware ARC child plan to switch which region runs the scheduled refresh

import os
import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PRIMARY_REGION = os.environ.get('PRIMARY_REGION', 'us-east-1')
SECONDARY_REGION = os.environ.get('SECONDARY_REGION', 'us-east-2')
PRIMARY_RULE_NAME = os.environ['PRIMARY_RULE_NAME']
SECONDARY_RULE_NAME = os.environ['SECONDARY_RULE_NAME']


def lambda_handler(event: dict, context) -> dict:
    """Toggle EventBridge schedule rules based on which region is activating."""
    logger.info(f"Toggle event: {json.dumps(event)}")

    # Determine which region is activating from the ARC event
    # ARC passes the activating region in the event payload
    activating_region = os.environ.get('AWS_REGION', PRIMARY_REGION)
    logger.info(f"Running in region: {activating_region}")

    # Enable schedule in the activating region, disable in the other
    if activating_region == PRIMARY_REGION:
        enable_region, enable_rule = PRIMARY_REGION, PRIMARY_RULE_NAME
        disable_region, disable_rule = SECONDARY_REGION, SECONDARY_RULE_NAME
    else:
        enable_region, enable_rule = SECONDARY_REGION, SECONDARY_RULE_NAME
        disable_region, disable_rule = PRIMARY_REGION, PRIMARY_RULE_NAME

    # Enable the schedule in the activating region
    events_enable = boto3.client('events', region_name=enable_region)
    events_enable.enable_rule(Name=enable_rule)
    logger.info(f"Enabled rule {enable_rule} in {enable_region}")

    # Disable the schedule in the deactivating region
    events_disable = boto3.client('events', region_name=disable_region)
    events_disable.disable_rule(Name=disable_rule)
    logger.info(f"Disabled rule {disable_rule} in {disable_region}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'enabled': f'{enable_rule} in {enable_region}',
            'disabled': f'{disable_rule} in {disable_region}'
        })
    }

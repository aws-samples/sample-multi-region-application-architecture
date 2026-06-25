"""
Global Cluster Join — CloudFormation Custom Resource Lambda.

Joins a secondary DocumentDB regional cluster to an existing global cluster.
On DELETE, removes the regional cluster from the global cluster first.

This Lambda is only deployed in the secondary region. It uses the cfnresponse
pattern to signal success/failure back to CloudFormation.
"""

import json
import logging
import time
import urllib.request

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# boto3 RDS client — DocumentDB global cluster APIs live under the RDS namespace
rds = boto3.client("rds")


def send_cfn_response(event: dict, context, status: str, data: dict = None, reason: str = "") -> None:
    """
    Send a response back to CloudFormation to signal success or failure.

    CloudFormation Custom Resources require a PUT to a pre-signed S3 URL
    with the result status. This replaces the cfnresponse module so we
    don't need an extra dependency.
    """
    response_body = json.dumps({
        "Status": status,
        "Reason": reason or f"See CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": event.get("PhysicalResourceId", f"global-join-{event.get('StackId', 'unknown').split('/')[-1]}"),
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data or {},
    })

    # urllib.request.Request sends an HTTP request — here we PUT JSON to the CFN callback URL
    req = urllib.request.Request(
        event["ResponseURL"],
        data=response_body.encode("utf-8"),
        headers={"Content-Type": ""},
        method="PUT",
    )
    urllib.request.urlopen(req)
    logger.info(f"CFN response sent: {status}")


def wait_for_cluster_available(cluster_id: str, max_wait: int = 300) -> None:
    """
    Poll the regional cluster until its status is 'available'.

    Args:
        cluster_id: DocumentDB cluster identifier
        max_wait: Maximum seconds to wait
    """
    start = time.time()
    while time.time() - start < max_wait:
        response = rds.describe_db_clusters(DBClusterIdentifier=cluster_id)
        status = response["DBClusters"][0]["Status"]
        logger.info(f"Cluster {cluster_id} status: {status}")
        if status == "available":
            return
        time.sleep(15)  # nosemgrep: arbitrary-sleep


def handler(event: dict, context) -> None:
    """
    CloudFormation Custom Resource handler.

    ResourceProperties expected:
        GlobalClusterIdentifier: str — the global cluster to join
        RegionalClusterArn: str — the secondary regional cluster ARN

    On CREATE: adds regional cluster to global cluster
    On UPDATE: no-op
    On DELETE: removes regional cluster from global cluster
    """
    logger.info(f"Event: {json.dumps(event)}")

    request_type = event["RequestType"]
    props = event["ResourceProperties"]
    global_cluster_id = props["GlobalClusterIdentifier"]
    regional_cluster_arn = props["RegionalClusterArn"]

    try:
        if request_type == "Create":
            # The regional cluster is already joined to the global cluster
            # via the GlobalClusterIdentifier property in CloudFormation.
            # This custom resource now only handles DELETE (removing from global cluster).
            logger.info(f"Cluster {regional_cluster_arn} already joined to {global_cluster_id} via CloudFormation")
            send_cfn_response(event, context, "SUCCESS", {
                "GlobalClusterIdentifier": global_cluster_id,
            })

        elif request_type == "Update":
            # No-op — global cluster membership doesn't change on update
            logger.info("Update — no-op")
            send_cfn_response(event, context, "SUCCESS")

        elif request_type == "Delete":
            logger.info(f"Removing {regional_cluster_arn} from global cluster {global_cluster_id}")
            try:
                rds.remove_from_global_cluster(
                    GlobalClusterIdentifier=global_cluster_id,
                    DbClusterIdentifier=regional_cluster_arn,
                )
                logger.info("Successfully removed from global cluster")
            except ClientError as err:
                error_code = err.response["Error"]["Code"]
                # If cluster is already removed or doesn't exist, that's fine on delete
                if error_code in (
                    "DBClusterNotFoundFault",
                    "GlobalClusterNotFoundFault",
                    "InvalidDBClusterStateFault",
                ):
                    logger.warning(f"Ignoring error on delete: {err}")
                elif error_code == "InvalidParameterValue":
                    # This cluster may be the writer after failover.
                    # Remove all other members first, then delete the global cluster.
                    logger.info("Cluster is writer — removing other members and deleting global cluster")
                    try:
                        gc = rds.describe_global_clusters(GlobalClusterIdentifier=global_cluster_id)
                        members = gc["GlobalClusters"][0]["GlobalClusterMembers"]
                        # Remove non-writer members first
                        for member in members:
                            if not member["IsCluster"]:
                                continue
                            if member["DBClusterArn"] == regional_cluster_arn:
                                continue
                            logger.info(f"Removing member {member['DBClusterArn']}")
                            try:
                                rds.remove_from_global_cluster(
                                    GlobalClusterIdentifier=global_cluster_id,
                                    DbClusterIdentifier=member["DBClusterArn"],
                                )
                            except ClientError:
                                logger.warning(f"Could not remove {member['DBClusterArn']}, continuing")
                        # Now remove self (writer) — this detaches from global cluster
                        time.sleep(10)  # nosemgrep: arbitrary-sleep — DocumentDB needs propagation time between member removals
                        rds.remove_from_global_cluster(
                            GlobalClusterIdentifier=global_cluster_id,
                            DbClusterIdentifier=regional_cluster_arn,
                        )
                        # Delete the now-empty global cluster
                        time.sleep(5)  # nosemgrep: arbitrary-sleep — global cluster transitions through intermediate state
                        rds.delete_global_cluster(GlobalClusterIdentifier=global_cluster_id)
                        logger.info("Global cluster deleted")
                    except ClientError as inner_err:
                        logger.warning(f"Best-effort global cluster cleanup: {inner_err}")
                else:
                    raise

            send_cfn_response(event, context, "SUCCESS")

    except Exception as err:
        logger.error(f"Failed: {err}", exc_info=True)
        send_cfn_response(event, context, "FAILED", reason=str(err))

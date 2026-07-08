#!/usr/bin/env python3
"""
AirportHub Teardown Script - reliably removes all AirportHub resources from an AWS account.

Auto-discovers resources by prefix, handles dependency ordering, and retries on failure.
Addresses common teardown failures: VPC endpoint ENIs blocking subnets, ECR repos with
images, and DocumentDB global cluster ordering.

Usage:
    python3 teardown.py --profile admin-6278              # Interactive teardown
    python3 teardown.py --profile admin-6278 --dry-run    # List resources without deleting
    python3 teardown.py --profile admin-6278 --yes        # Skip confirmation prompt
"""

import argparse
import json
import logging
import subprocess
import sys
import time

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Rich (optional) ───────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None


def step_done(message: str) -> None:
    """Print a styled step-completion checkmark."""
    if RICH_AVAILABLE and console:
        console.print(f"  [bold green]✔[/bold green] {message}")
    else:
        print(f"  ✔ {message}")


def step_info(message: str) -> None:
    """Print an informational step message."""
    if RICH_AVAILABLE and console:
        console.print(f"  [dim]{message}[/dim]")
    else:
        print(f"  {message}")


def step_warn(message: str) -> None:
    """Print a warning message."""
    if RICH_AVAILABLE and console:
        console.print(f"  [yellow]⚠[/yellow] {message}")
    else:
        print(f"  ⚠ {message}")


def step_error(message: str) -> None:
    """Print an error message."""
    if RICH_AVAILABLE and console:
        console.print(f"  [bold red]✗[/bold red] {message}")
    else:
        print(f"  ✗ {message}")

# ── Constants ──────────────────────────────────────────────────────────────────
STACK_PREFIX = "airporthub"
REGIONS = ["us-east-1", "us-east-2"]
MAX_RETRIES = 3
POLL_INTERVAL_SECONDS = 15


# ═══════════════════════════════════════════════════════════════════════════════
# AWS Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_boto3_client(service: str, region: str, profile: str):
    """
    Create a boto3 client for the given service, region, and profile.

    Uses boto3.Session to respect the --profile argument, similar to how
    the AWS CLI uses named profiles from ~/.aws/credentials.
    """
    import boto3
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client(service)


def run_aws(cmd: list[str], profile: str, region: str, quiet: bool = False) -> dict:
    """
    Execute an AWS CLI command and return parsed JSON output.

    Builds the subprocess argument list directly (no shell interpolation or
    string splitting), which prevents command injection and ensures arguments
    with special characters are passed correctly.

    Args:
        cmd: AWS CLI command as a list of individual arguments,
             e.g. ["cloudformation", "delete-stack", "--stack-name", "my-stack"]
        profile: AWS CLI profile name
        region: AWS region
        quiet: Suppress error logging

    Returns:
        Parsed JSON response dict, or empty dict if no output
    """
    # Build the full command as a list - each element is one argument, so
    # subprocess passes them directly to the OS without shell parsing.
    full_cmd = ["aws"] + cmd + ["--region", region, "--profile", profile, "--output", "json"]
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if not quiet:
            logger.error(f"AWS CLI error: {result.stderr.strip()}")
        return {}
    return json.loads(result.stdout) if result.stdout.strip() else {}


# ═══════════════════════════════════════════════════════════════════════════════
# Resource Discovery
# ═══════════════════════════════════════════════════════════════════════════════

def discover_resources(profile: str) -> dict:
    """
    Discover all AirportHub resources across both regions.

    Scans CloudFormation stacks, S3 buckets, ECR repos, and DocumentDB
    global clusters. Returns a dict of categorized resources.
    """
    step_info("Discovering AirportHub resources...")
    resources = {
        "stacks": {},
        "s3_buckets": [],
        "ecr_repos": {},
        "docdb_global_clusters": [],
    }

    # CloudFormation stacks in both regions
    for region in REGIONS:
        # Include all non-deleted states
        status_filter = [
            "CREATE_COMPLETE", "UPDATE_COMPLETE", "ROLLBACK_COMPLETE",
            "UPDATE_ROLLBACK_COMPLETE", "CREATE_IN_PROGRESS", "DELETE_FAILED",
            "ROLLBACK_FAILED", "DELETE_IN_PROGRESS",
        ]
        resp = run_aws(
            ["cloudformation", "list-stacks", "--stack-status-filter"] + status_filter,
            profile, region, quiet=True
        )
        stacks = [
            {"name": s["StackName"], "status": s["StackStatus"]}
            for s in resp.get("StackSummaries", [])
            if STACK_PREFIX in s["StackName"].lower() or "flightaware" in s["StackName"].lower()
        ]
        if stacks:
            resources["stacks"][region] = stacks

    # S3 buckets (global - query from us-east-1)
    resp = run_aws(["s3api", "list-buckets"], profile, "us-east-1", quiet=True)
    resources["s3_buckets"] = [
        b["Name"] for b in resp.get("Buckets", [])
        if STACK_PREFIX in b["Name"]
    ]

    # ECR repos in both regions
    for region in REGIONS:
        resp = run_aws(["ecr", "describe-repositories"], profile, region, quiet=True)
        repos = [
            r["repositoryName"] for r in resp.get("repositories", [])
            if STACK_PREFIX in r["repositoryName"]
        ]
        if repos:
            resources["ecr_repos"][region] = repos

    # DocumentDB global clusters
    resp = run_aws(["docdb", "describe-global-clusters"], profile, "us-east-1", quiet=True)
    resources["docdb_global_clusters"] = [
        gc["GlobalClusterIdentifier"] for gc in resp.get("GlobalClusters", [])
        if STACK_PREFIX in gc["GlobalClusterIdentifier"]
    ]

    return resources


def print_discovery(resources: dict) -> None:
    """Print discovered resources in a readable format."""
    total = 0

    if resources["stacks"]:
        step_info("CloudFormation Stacks:")
        for region, stacks in resources["stacks"].items():
            for s in stacks:
                print(f"      [{region}] {s['name']} ({s['status']})")
                total += 1

    if resources["s3_buckets"]:
        step_info("S3 Buckets:")
        for b in resources["s3_buckets"]:
            print(f"      {b}")
            total += 1

    if resources["ecr_repos"]:
        step_info("ECR Repositories:")
        for region, repos in resources["ecr_repos"].items():
            for r in repos:
                print(f"      [{region}] {r}")
                total += 1

    if resources["docdb_global_clusters"]:
        step_info("DocumentDB Global Clusters:")
        for gc in resources["docdb_global_clusters"]:
            print(f"      {gc}")
            total += 1

    if total == 0:
        step_info("No AirportHub resources found. Account is clean.")

    return total


# ═══════════════════════════════════════════════════════════════════════════════
# Pre-Cleanup (removes dependencies that block stack deletion)
# ═══════════════════════════════════════════════════════════════════════════════

def delete_vpc_endpoints(profile: str) -> bool:
    """
    Delete all VPC endpoints in airporthub VPCs across both regions.

    VPC endpoint ENIs block subnet deletion. Removing endpoints first
    ensures CloudFormation can cleanly delete the NetworkStack.
    """
    found = False
    for region in REGIONS:
        resp = run_aws(["ec2", "describe-vpc-endpoints"], profile, region, quiet=True)
        vpce_ids = []
        for ep in resp.get("VpcEndpoints", []):
            if ep.get("State") == "deleted":
                continue
            tags = {t["Key"]: t["Value"] for t in ep.get("Tags", [])}
            if "airporthub" in str(tags).lower() or "AirportHub" in tags.get("Project", ""):
                vpce_ids.append(ep["VpcEndpointId"])

        if vpce_ids:
            found = True
            run_aws(
                ["ec2", "delete-vpc-endpoints", "--vpc-endpoint-ids"] + vpce_ids,
                profile, region
            )
            step_done(f"Deleted {len(vpce_ids)} VPC endpoint(s) in {region}")
    return found


def empty_ecr_repos(profile: str) -> bool:
    """
    Delete all images and force-delete ECR repos in both regions.

    ECR repos with images cannot be deleted by CloudFormation. Pre-cleaning
    ensures the ComputeStack deletion succeeds.
    """
    found = False
    for region in REGIONS:
        resp = run_aws(["ecr", "describe-repositories"], profile, region, quiet=True)
        for repo in resp.get("repositories", []):
            if STACK_PREFIX not in repo["repositoryName"]:
                continue
            found = True
            repo_name = repo["repositoryName"]
            # List and delete all images
            images_resp = run_aws(
                ["ecr", "list-images", "--repository-name", repo_name],
                profile, region, quiet=True
            )
            image_ids = images_resp.get("imageIds", [])
            if image_ids:
                # batch-delete-image accepts JSON
                ids_json = json.dumps(image_ids)
                client = get_boto3_client("ecr", region, profile)
                client.batch_delete_image(repositoryName=repo_name, imageIds=image_ids)
                step_done(f"Deleted {len(image_ids)} image(s) from {repo_name} in {region}")

            # Force-delete the repo
            client = get_boto3_client("ecr", region, profile)
            try:
                client.delete_repository(repositoryName=repo_name, force=True)
                step_done(f"Deleted ECR repo {repo_name} in {region}")
            except Exception as e:
                step_warn(f"Could not delete ECR repo {repo_name}: {e}")
    return found


def remove_docdb_secondary(profile: str) -> bool:
    """
    Remove secondary cluster from DocumentDB global cluster.

    The global cluster cannot be deleted while secondary clusters are attached.
    This must happen before the primary stack (which owns the global cluster) is deleted.
    """
    resp = run_aws(["docdb", "describe-global-clusters"], profile, "us-east-1", quiet=True)
    found = False
    for gc in resp.get("GlobalClusters", []):
        if STACK_PREFIX not in gc["GlobalClusterIdentifier"]:
            continue
        # Find secondary members
        for member in gc.get("GlobalClusterMembers", []):
            if not member.get("IsWriter", False):
                found = True
                cluster_arn = member["DBClusterArn"]
                gc_id = gc["GlobalClusterIdentifier"]
                client = get_boto3_client("docdb", "us-east-1", profile)
                try:
                    client.remove_from_global_cluster(
                        GlobalClusterIdentifier=gc_id,
                        DbClusterIdentifier=cluster_arn
                    )
                    step_done(f"Removed secondary cluster from global cluster {gc_id}")
                    # Wait for the detached cluster to become standalone (takes ~60-90s)
                    step_info(f"Waiting for secondary cluster to stabilize...")
                    time.sleep(60)
                except Exception as e:
                    step_warn(f"Could not remove secondary from global cluster: {e}")
    return found


def empty_s3_buckets(profile: str) -> None:
    """
    Empty all airporthub S3 buckets (templates and ARC reports).

    S3 buckets must be empty before deletion. CloudFormation cannot delete
    non-empty buckets.
    """
    resp = run_aws(["s3api", "list-buckets"], profile, "us-east-1", quiet=True)
    for bucket in resp.get("Buckets", []):
        if STACK_PREFIX not in bucket["Name"]:
            continue
        bucket_name = bucket["Name"]
        # Determine bucket region
        try:
            loc = run_aws(
                ["s3api", "get-bucket-location", "--bucket", bucket_name],
                profile, "us-east-1", quiet=True
            )
            bucket_region = loc.get("LocationConstraint") or "us-east-1"
        except Exception:
            bucket_region = "us-east-1"

        # List and delete all objects
        client = get_boto3_client("s3", bucket_region, profile)
        try:
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket_name):
                objects = page.get("Contents", [])
                if objects:
                    delete_keys = [{"Key": o["Key"]} for o in objects]
                    client.delete_objects(
                        Bucket=bucket_name,
                        Delete={"Objects": delete_keys}
                    )
            # Delete the bucket
            client.delete_bucket(Bucket=bucket_name)
            step_done(f"Deleted S3 bucket: {bucket_name}")
        except Exception as e:
            step_warn(f"Could not delete bucket {bucket_name}: {e}")


def _empty_arc_reports_bucket(profile: str) -> None:
    """
    Empty the ARC Region Switch execution reports bucket.

    ARC writes execution reports to airporthub-arc-reports-<account_id> during
    plan executions. This bucket must be empty before the ARC plan stack can
    be deleted by CloudFormation.
    """
    # Get account ID to construct bucket name
    identity = run_aws(["sts", "get-caller-identity"], profile, "us-east-1", quiet=True)
    account_id = identity.get("Account", "")
    if not account_id:
        return

    bucket_name = f"{STACK_PREFIX}-arc-reports-{account_id}"
    client = get_boto3_client("s3", "us-east-1", profile)
    try:
        paginator = client.get_paginator("list_objects_v2")
        deleted_count = 0
        for page in paginator.paginate(Bucket=bucket_name):
            objects = page.get("Contents", [])
            if objects:
                delete_keys = [{"Key": o["Key"]} for o in objects]
                client.delete_objects(
                    Bucket=bucket_name,
                    Delete={"Objects": delete_keys}
                )
                deleted_count += len(delete_keys)
        if deleted_count > 0:
            step_done(f"Emptied ARC reports bucket: {deleted_count} object(s) removed")
    except client.exceptions.NoSuchBucket:
        pass  # Bucket doesn't exist - nothing to clean
    except Exception as e:
        step_warn(f"Could not empty ARC reports bucket: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# Stack Deletion with Retry
# ═══════════════════════════════════════════════════════════════════════════════

def _cfn_console_url(stack_name: str, region: str) -> str:
    """Generate a direct CloudFormation console URL for a stack."""
    return f"https://{region}.console.aws.amazon.com/cloudformation/home?region={region}#/stacks"


def delete_stack_with_retry(stack_name: str, region: str, profile: str) -> bool:
    """
    Delete a CloudFormation stack with polling and retry on failure.

    Waits for deletion to complete. On DELETE_FAILED, attempts to identify
    the blocking resource, clean it up, and retry.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region
        profile: AWS CLI profile

    Returns:
        True if stack was deleted, False if it could not be deleted after retries
    """
    for attempt in range(1, MAX_RETRIES + 1):
        # Check current state
        resp = run_aws(
            ["cloudformation", "describe-stacks", "--stack-name", stack_name],
            profile, region, quiet=True
        )
        if not resp.get("Stacks"):
            step_done(f"{stack_name} deleted")
            return True

        status = resp["Stacks"][0]["StackStatus"]
        if status == "DELETE_COMPLETE":
            step_done(f"{stack_name} deleted")
            return True
        if status == "DELETE_IN_PROGRESS":
            step_info(f"Waiting for {stack_name} to finish deleting...")
        else:
            # Initiate deletion
            run_aws(["cloudformation", "delete-stack", "--stack-name", stack_name], profile, region)
            step_info(f"Deleting {stack_name} (attempt {attempt}/{MAX_RETRIES})...")

        # Poll until complete or failed
        while True:
            time.sleep(POLL_INTERVAL_SECONDS)
            resp = run_aws(
                ["cloudformation", "describe-stacks", "--stack-name", stack_name],
                profile, region, quiet=True
            )
            if not resp.get("Stacks"):
                step_done(f"{stack_name} deleted")
                return True

            status = resp["Stacks"][0]["StackStatus"]
            if status == "DELETE_COMPLETE":
                step_done(f"{stack_name} deleted")
                return True
            elif status == "DELETE_FAILED":
                reason = resp["Stacks"][0].get("StackStatusReason", "Unknown")
                step_warn(f"Delete failed: {reason}")
                if attempt < MAX_RETRIES:
                    step_info(f"Attempting automatic remediation...")
                    _remediate_delete_failure(stack_name, region, profile)
                break  # Retry
            elif status != "DELETE_IN_PROGRESS":
                # Unexpected state - try to delete anyway
                run_aws(["cloudformation", "delete-stack", "--stack-name", stack_name], profile, region)
                break

    # All retries exhausted — provide actionable guidance
    step_error(f"Could not delete {stack_name} after {MAX_RETRIES} attempts")
    step_info(f"Manual cleanup required. View stack in console:")
    step_info(f"  {_cfn_console_url(stack_name, region)}")
    step_info(f"Tip: Check the Events tab for the specific resource blocking deletion.")
    return False


def _remediate_delete_failure(stack_name: str, region: str, profile: str) -> None:
    """
    Attempt to fix common DELETE_FAILED causes.

    Checks stack events for failure reasons and takes corrective action:
    - Subnet dependency → delete VPC endpoints, wait for ENI release
    - ECR images → force-delete images
    """
    resp = run_aws(
        ["cloudformation", "describe-stack-events", "--stack-name", stack_name],
        profile, region, quiet=True
    )
    for event in resp.get("StackEvents", []):
        if event.get("ResourceStatus") != "DELETE_FAILED":
            continue
        reason = event.get("ResourceStatusReason", "")

        if "subnet" in reason.lower() and "dependencies" in reason.lower():
            step_info("  → Subnet has dependencies (VPC endpoint ENIs). Removing them...")
            delete_vpc_endpoints(profile)
            time.sleep(10)  # Wait for ENIs to release

        elif "still contains images" in reason.lower():
            step_info("  → ECR repository contains images. Clearing them...")
            empty_ecr_repos(profile)

        elif "bucket is not empty" in reason.lower() or "BucketNotEmpty" in reason:
            step_info("  → S3 bucket is not empty. Emptying it...")
            _empty_arc_reports_bucket(profile)
            empty_s3_buckets(profile)

        elif "DatabaseStack" in reason or "DBCluster" in reason.lower():
            step_info("  → DocumentDB cluster still modifying. Waiting and retrying...")
            _remediate_database_stack(stack_name, region, profile)
            _remediate_docdb_cluster(stack_name, region, profile)

        elif "GlobalClusterJoin" in reason or "Custom::" in reason:
            step_info("  → Custom resource already handled. Skipping it on retry...")
            _retry_delete_with_retain(stack_name, region, profile)


def _remediate_docdb_cluster(stack_name: str, region: str, profile: str) -> None:
    """
    Handle DocumentDB cluster deletion failures.

    After RemoveFromGlobalCluster, the secondary cluster becomes standalone but
    may still be modifying. We wait for it to stabilize, delete its instances,
    then delete the cluster itself (skip-final-snapshot).
    """
    client = get_boto3_client("docdb", region, profile)

    # Find airporthub clusters in this region
    try:
        resp = client.describe_db_clusters()
        clusters = [c for c in resp.get("DBClusters", []) if STACK_PREFIX in c["DBClusterIdentifier"]]
    except Exception:
        return

    for cluster in clusters:
        cluster_id = cluster["DBClusterIdentifier"]
        status = cluster["Status"]
        step_info(f"DocumentDB cluster {cluster_id} status: {status}")

        # Wait for cluster to become available (max 5 min)
        wait_count = 0
        while status not in ("available", "stopped") and wait_count < 20:
            time.sleep(15)
            wait_count += 1
            try:
                resp = client.describe_db_clusters(DBClusterIdentifier=cluster_id)
                status = resp["DBClusters"][0]["Status"]
            except Exception:
                break

        # Delete instances first (required before cluster deletion)
        for member in cluster.get("DBClusterMembers", []):
            instance_id = member["DBInstanceIdentifier"]
            try:
                client.delete_db_instance(DBInstanceIdentifier=instance_id)
                step_info(f"Deleting DocumentDB instance: {instance_id}")
            except Exception as e:
                if "not found" not in str(e).lower():
                    step_warn(f"Could not delete instance {instance_id}: {e}")

        # Wait for instances to be deleted (max 5 min)
        time.sleep(30)

        # Delete the cluster
        try:
            client.delete_db_cluster(
                DBClusterIdentifier=cluster_id,
                SkipFinalSnapshot=True
            )
            step_info(f"Deleting DocumentDB cluster: {cluster_id}")
        except Exception as e:
            if "not found" not in str(e).lower():
                step_warn(f"Could not delete cluster {cluster_id}: {e}")

    # Wait for deletion to propagate before CloudFormation retry
    time.sleep(30)


def _remediate_database_stack(parent_stack: str, region: str, profile: str) -> None:
    """
    Handle DatabaseStack deletion failure caused by GlobalClusterJoinCustomResource.

    The custom resource fails on DELETE because we already detached the cluster
    from the global cluster in pre-cleanup. Fix: find the nested DatabaseStack
    and delete it with --retain-resources on the custom resource.
    """
    # Find the nested DatabaseStack physical name
    resp = run_aws(
        ["cloudformation", "list-stack-resources", "--stack-name", parent_stack],
        profile, region, quiet=True
    )
    for resource in resp.get("StackResourceSummaries", []):
        if "DatabaseStack" in resource.get("LogicalResourceId", ""):
            nested_stack_name = resource.get("PhysicalResourceId", "")
            if not nested_stack_name or "arn:" in nested_stack_name:
                # Extract stack name from ARN
                nested_stack_name = nested_stack_name.split("/")[1] if "/" in nested_stack_name else ""
            if nested_stack_name:
                step_info(f"Retrying DatabaseStack deletion, retaining GlobalClusterJoinCustomResource...")
                run_aws(
                    ["cloudformation", "delete-stack", "--stack-name", nested_stack_name,
                     "--retain-resources", "GlobalClusterJoinCustomResource"],
                    profile, region
                )
                # Wait for nested stack to delete
                time.sleep(30)
                return


def _retry_delete_with_retain(stack_name: str, region: str, profile: str) -> None:
    """
    Retry stack deletion by retaining resources that failed to delete.

    When a custom resource fails on DELETE (e.g., GlobalClusterJoin after we
    already detached the cluster), we identify the failed resources and retry
    with --retain-resources to skip them. The underlying resources are already
    cleaned up by our pre-cleanup phase.
    """
    # Find which resources failed
    resp = run_aws(
        ["cloudformation", "describe-stack-events", "--stack-name", stack_name],
        profile, region, quiet=True
    )
    failed_resources = []
    for event in resp.get("StackEvents", []):
        if event.get("ResourceStatus") == "DELETE_FAILED":
            logical_id = event.get("LogicalResourceId", "")
            if logical_id and logical_id != stack_name:
                failed_resources.append(logical_id)

    if failed_resources:
        # De-duplicate
        failed_resources = list(set(failed_resources))
        step_info(f"Retaining failed resources: {' '.join(failed_resources)}")
        run_aws(
            ["cloudformation", "delete-stack", "--stack-name", stack_name,
             "--retain-resources"] + failed_resources,
            profile, region
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Main Teardown Orchestration
# ═══════════════════════════════════════════════════════════════════════════════

def run_teardown(profile: str) -> None:
    """
    Execute the full teardown sequence with parallelism where safe.

    Order:
    1. Pre-cleanup in parallel (VPC endpoints, ECR, DocumentDB)
    2. FlightAware stacks + ARC plan in parallel
    3. Secondary + Primary master stacks (secondary first, then primary)
    4. Orphaned stacks cleanup
    5. S3 buckets
    """
    import concurrent.futures

    print("")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  [1/4] Pre-cleanup (VPC endpoints, ECR, DocumentDB)")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Pre-cleanup steps are independent — run in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(delete_vpc_endpoints, profile),
            executor.submit(empty_ecr_repos, profile),
            executor.submit(remove_docdb_secondary, profile),
        ]
        results = [f.result() for f in futures]
    # If nothing was cleaned, inform the operator
    if not any(results):
        step_info("Nothing to pre-clean — dependencies already removed")

    print("")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  [2/4] FlightAware + ARC plan (parallel)")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # FlightAware stacks (both regions) + ARC plan are independent — run in parallel
    def _delete_flightaware():
        found = False
        for region in REGIONS:
            stack_name = f"flightaware-app-switchover-{region}"
            resp = run_aws(
                ["cloudformation", "describe-stacks", "--stack-name", stack_name],
                profile, region, quiet=True
            )
            if resp.get("Stacks"):
                found = True
                delete_stack_with_retry(stack_name, region, profile)
        return found

    def _delete_arc_plan():
        resp = run_aws(
            ["cloudformation", "describe-stacks", "--stack-name", f"{STACK_PREFIX}-arc-plan"],
            profile, "us-east-1", quiet=True
        )
        if resp.get("Stacks"):
            _empty_arc_reports_bucket(profile)
            empty_s3_buckets(profile)
            delete_stack_with_retry(f"{STACK_PREFIX}-arc-plan", "us-east-1", profile)
            return True
        return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_delete_flightaware),
            executor.submit(_delete_arc_plan),
        ]
        results = [f.result() for f in futures]
    if not any(results):
        step_info("No FlightAware or ARC plan stacks found — skipped")

    print("")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  [3/4] Master stacks (secondary then primary)")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Secondary master stack — must complete before primary (DocumentDB global cluster)
    resp = run_aws(
        ["cloudformation", "describe-stacks", "--stack-name", f"{STACK_PREFIX}-us-east-2"],
        profile, "us-east-2", quiet=True
    )
    if resp.get("Stacks"):
        delete_stack_with_retry(f"{STACK_PREFIX}-us-east-2", "us-east-2", profile)

    # Primary master stack (cascades to all nested stacks)
    resp = run_aws(
        ["cloudformation", "describe-stacks", "--stack-name", f"{STACK_PREFIX}-us-east-1"],
        profile, "us-east-1", quiet=True
    )
    if resp.get("Stacks"):
        delete_stack_with_retry(f"{STACK_PREFIX}-us-east-1", "us-east-1", profile)

    # Cleanup any orphaned nested stacks that survived parent deletion
    for region in REGIONS:
        resp = run_aws(
            ["cloudformation", "list-stacks", "--stack-status-filter",
             "DELETE_FAILED", "CREATE_COMPLETE", "ROLLBACK_COMPLETE", "ROLLBACK_FAILED"],
            profile, region, quiet=True
        )
        for stack in resp.get("StackSummaries", []):
            if STACK_PREFIX in stack["StackName"].lower():
                delete_stack_with_retry(stack["StackName"], region, profile)

    print("")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  [4/4] S3 bucket cleanup")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    empty_s3_buckets(profile)

    print("")
    step_done("Teardown complete!")
    print("")

# ═══════════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """
    Parse arguments and run teardown.

    Supports:
      --profile  : AWS CLI profile (required)
      --dry-run  : Discover resources without deleting
      --yes      : Skip confirmation prompt
    """
    parser = argparse.ArgumentParser(
        description="AirportHub Teardown - reliably removes all resources from an AWS account"
    )
    parser.add_argument(
        "--profile", required=True,
        help="AWS CLI profile name (e.g., admin-6278)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List resources that would be deleted without taking action"
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt"
    )
    args = parser.parse_args()

    # Verify AWS credentials
    identity = run_aws(["sts", "get-caller-identity"], args.profile, "us-east-1")
    if not identity:
        step_error("Failed to authenticate. Check your AWS profile and credentials.")
        sys.exit(1)

    account_id = identity.get("Account", "unknown")

    # ── Configuration summary ──────────────────────────────────────────────
    print("")
    print("=" * 60)
    print("  AirportHub Deployment Configuration")
    print("=" * 60)
    print("")
    print(f"  Primary stack:   {STACK_PREFIX}-us-east-1")
    print(f"  Secondary stack: {STACK_PREFIX}-us-east-2")
    print(f"  Account:         {account_id}")
    print("")

    # Discover resources
    resources = discover_resources(args.profile)
    total = print_discovery(resources)

    if total == 0:
        print("")
        print("  Nothing to tear down. Account is clean.")
        sys.exit(0)

    if args.dry_run:
        print("")
        print("  DRY RUN — no changes made.")
        sys.exit(0)

    # ── Teardown warning panel ─────────────────────────────────────────────
    print("")
    print("=" * 60)
    print("  🚨 AirportHub TEARDOWN")
    print("=" * 60)
    print("")
    print("  This will DELETE all resources in:")
    print(f"    Primary:     {STACK_PREFIX}-us-east-1 (us-east-1)")
    print(f"    Secondary:   {STACK_PREFIX}-us-east-2 (us-east-2)")
    print(f"    ARC Plan:    {STACK_PREFIX}-arc-plan")
    print(f"    FlightAware: flightaware-app-switchover (both regions)")
    print(f"    S3 Buckets:  {STACK_PREFIX}-templates-* (both regions)")
    print("")

    # Confirm
    if not args.yes:
        response = input("  Type 'yes' to confirm teardown: ")
        if response.strip().lower() != "yes":
            print("  Aborted.")
            sys.exit(0)

    print("")
    print("  " + "━" * 56)
    print(f"  🗑️  Confirmed. Deleting all AirportHub resources from account {account_id}")
    print("  " + "━" * 56)
    print("  Press Ctrl+C at any time to abort.")
    print("")

    run_teardown(args.profile)

    # Final verification
    print("")
    step_info("Verifying account is clean...")
    remaining = discover_resources(args.profile)
    remaining_count = sum(
        len(v) if isinstance(v, list) else sum(len(s) for s in v.values())
        for v in remaining.values() if v
    )
    if remaining_count == 0:
        print("  ✅ All AirportHub resources removed successfully.")
    else:
        print(f"  ⚠️  {remaining_count} resource(s) still remain. Manual cleanup may be needed.")
        print_discovery(remaining)

    print("")
    print("  To redeploy: python3 deploy.py --profile " + args.profile)
    print("")


if __name__ == "__main__":
    main()

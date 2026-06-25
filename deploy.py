#!/usr/bin/env python3
"""
AirportHub Deploy Script — guided interactive deployment and teardown.

Usage:
    python deploy.py                              # Interactive guided deploy
    python deploy.py --update-only                # Fast: refresh API key, rebuild container, hot-swap ECS
    python deploy.py --teardown                   # Teardown all resources
    python deploy.py --profile my-profile         # Deploy to a specific AWS profile

Deployment steps:
    1. Install Lambda dependencies (pip3 install into each Lambda directory)
    2. Create S3 bucket and package nested CloudFormation templates
    3. Deploy primary region master stack (Network, Auth, Database, Compute, API, Observability)
    4. Build container image via CodeBuild
    5. Deploy secondary region master stack (Network, Database, Compute, API, Observability)
    6. Deploy FlightAware scheduled-refresh microservice (both regions)
    7. Deploy ARC Region Switch recovery plan (primary region)

Update-only mode (--update-only):
    Skips all CloudFormation stack operations. Refreshes the FlightAware API
    key in Secrets Manager, rebuilds the container image via CodeBuild, and
    forces a new ECS deployment. Use after app code changes or API key rotation.
"""

import argparse
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time

# rich — provides progress bars, panels, and styled console output.
# Install with: pip3 install rich
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Rich console instance — used for styled output throughout the script
console = Console() if RICH_AVAILABLE else None


# ---------------------------------------------------------------------------
# Helper: Step-based progress tracker using rich
# ---------------------------------------------------------------------------
def create_progress_bar() -> "Progress | None":
    """
    Create a rich Progress bar configured for step-based tracking.

    Returns a Progress instance if rich is available, otherwise None.
    The progress bar shows: spinner, step description, bar, fraction, elapsed time.
    """
    if not RICH_AVAILABLE:
        return None
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def step_done(message: str) -> None:
    """
    Print a styled step-completion message using rich markup.

    Uses green checkmark and bold text to make completed steps stand out
    in the terminal output above the progress bar.

    Args:
        message: Human-readable summary of what just completed.
    """
    if RICH_AVAILABLE and console:
        console.print(f"  [bold green]✔[/bold green] {message}")
    else:
        logger.info(f"  ✔ {message}")


def show_deployment_plan(config: dict) -> None:
    """
    Display a deployment plan summary and require acknowledgment before proceeding.

    Shows the full scope of what will be deployed across both regions so the
    developer understands the blast radius before committing to a long-running deploy.
    """
    plan_text = f"""\
[bold yellow]Heads up:[/bold yellow] This deploys a full multi-region active/passive architecture.
[bold red]This will take over an hour.[/bold red]

[bold cyan]us-east-1 (primary - active)          us-east-2 (secondary - pilot light)[/bold cyan]
  • VPC + 4 subnets                       • VPC + 4 subnets
  • Cognito User Pool + App Client        • DocumentDB Regional Cluster (joins global)
  • DocumentDB Global Cluster (2 inst.)   • ECS Fargate Service (0 tasks)
  • ECS Fargate Service (2 tasks)         • Internal ALB + CloudFront VPC Origin
  • Internal ALB + CloudFront VPC Origin  • Lambda functions x3
  • Lambda functions x3                   • CloudWatch Dashboard + Alarms
  • CloudFront Distribution
  • CodeBuild project (container image)
  • CloudWatch Dashboard + Alarms

[bold cyan]Cross-region:[/bold cyan]
  • FlightAware scheduled-refresh microservice (both regions)
  • ARC Region Switch Plan (automated DR failover)
"""

    if RICH_AVAILABLE and console:
        console.print()
        console.print(Panel(
            plan_text,
            title="[bold]AirportHub Deployment Plan[/bold]",
            border_style="blue",
            padding=(1, 2),
        ))
    else:
        # Plain text fallback with ANSI colors
        CYAN = "\033[36m"
        YELLOW = "\033[33m"
        RED = "\033[31m"
        RESET = "\033[0m"
        print("\n" + "=" * 60)
        print(f"  {CYAN}AirportHub Deployment Plan{RESET}")
        print("=" * 60)
        print(f"\n  Account:  {config['account_id']}")
        print(f"  Profile:  {AWS_PROFILE or 'default'}")
        print()
        print(f"  {YELLOW}Heads up:{RESET} This deploys a full multi-region active/passive")
        print(f"  architecture across two AWS regions.")
        print(f"  {RED}This will take over an hour.{RESET}")
        print()
        print(f"  {CYAN}us-east-1 (primary - active):{RESET}")
        print("    • VPC + 4 subnets (2 public, 2 private)")
        print("    • Cognito User Pool + App Client")
        print("    • DocumentDB Global Cluster (2 instances)")
        print("    • ECS Fargate Service (2 tasks)")
        print("    • Internal ALB + CloudFront VPC Origin")
        print("    • Lambda functions x3 (airports, flights, crew)")
        print("    • CloudFront Distribution")
        print("    • CodeBuild project (container image)")
        print("    • CloudWatch Dashboard + Alarms")
        print()
        print(f"  {CYAN}us-east-2 (secondary - pilot light):{RESET}")
        print("    • VPC + 4 subnets (2 public, 2 private)")
        print("    • DocumentDB Regional Cluster (joins global)")
        print("    • ECS Fargate Service (0 tasks - scaled by ARC)")
        print("    • Internal ALB + CloudFront VPC Origin")
        print("    • Lambda functions x3 (airports, flights, crew)")
        print("    • CloudWatch Dashboard + Alarms")
        print()
        print(f"  {CYAN}Cross-region:{RESET}")
        print("    • FlightAware scheduled-refresh microservice (both regions)")
        print("    • ARC Region Switch Plan (automated DR failover)")
        print()

    # Require explicit acknowledgment before proceeding
    confirm = input("  Type 'agree' to deploy: ")
    if confirm.strip().lower() != "agree":
        logger.info("Deployment aborted by user.")
        sys.exit(0)

    print("\n  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  🚀 Launching full multi-region deployment...")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  You can see the status in AWS CloudFormation console.")
    print("  Press Ctrl+C at any time to abort (deployed resources remain).\n")

# Configure colored logging — makes deploy output easier to scan
class ColorFormatter(logging.Formatter):
    """Custom formatter that adds ANSI colors based on log level."""
    COLORS = {
        logging.DEBUG:    "\033[90m",       # grey
        logging.INFO:     "\033[36m",       # cyan
        logging.WARNING:  "\033[33m",       # yellow
        logging.ERROR:    "\033[31m",       # red
        logging.CRITICAL: "\033[1;31m",     # bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        record.msg = f"{color}{record.msg}{self.RESET}"
        return super().format(record)

# When rich is available, use RichHandler — it routes log output through rich's
# console, which coordinates with the progress bar so logs render above the bar
# instead of overlapping with it.
if RICH_AVAILABLE:
    from rich.logging import RichHandler
    handler = RichHandler(console=console, show_time=True, show_path=False, markup=True)
    handler.setFormatter(logging.Formatter("%(message)s", datefmt="%Y-%m-%dT%H:%M:%S"))
else:
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"))
logging.basicConfig(level=logging.WARNING, handlers=[handler])
logger = logging.getLogger("deploy")

# Global AWS profile — set via --profile flag, injected into every AWS CLI call
AWS_PROFILE: str | None = None


# ---------------------------------------------------------------------------
# Helper: run an AWS CLI command and return parsed JSON output
# ---------------------------------------------------------------------------
def run_aws(command: str, region: str, capture: bool = True, quiet: bool = False) -> dict:
    """
    Execute an AWS CLI command with the given region.

    Args:
        command: AWS CLI command (without 'aws' prefix), e.g. 'sts get-caller-identity'
        region: AWS region code
        capture: If True, parse and return JSON output; if False, stream output
        quiet: If True, suppress error logging (caller handles the error)

    Returns:
        Parsed JSON response as dict, or empty dict if capture=False
    """
    profile_flag = f" --profile {AWS_PROFILE}" if AWS_PROFILE else ""
    full_cmd = f"aws {command} --region {region}{profile_flag} --output json"
    # Log the command being run
    logger.info(f"Running: {full_cmd}")

    # Use shlex.split for safe command execution without shell=True
    cmd_args = shlex.split(full_cmd)

    if capture:
        result = subprocess.run(  # nosemgrep: dangerous-subprocess-use-audit
            cmd_args, capture_output=True, text=True
        )
        if result.returncode != 0:
            if not quiet:
                logger.error(f"Command failed: {result.stderr.strip()}")
            raise RuntimeError(f"AWS CLI error: {result.stderr.strip()}")
        return json.loads(result.stdout) if result.stdout.strip() else {}
    else:
        # Stream output to console (for long-running commands)
        result = subprocess.run(cmd_args)  # nosemgrep: dangerous-subprocess-use-audit
        if result.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {result.returncode}")
        return {}


def stack_exists(stack_name: str, region: str) -> bool:
    """Check if a CloudFormation stack exists (any status except DELETE_COMPLETE)."""
    try:
        resp = run_aws(f"cloudformation describe-stacks --stack-name {stack_name}", region=region, quiet=True)
        status = resp.get("Stacks", [{}])[0].get("StackStatus", "")
        return "DELETE_COMPLETE" not in status
    except RuntimeError:
        return False


# ---------------------------------------------------------------------------
# Step 1: Validate prerequisites
# ---------------------------------------------------------------------------
def validate_prerequisites() -> None:
    """
    Check that required tools are installed and AWS auth is valid.
    Raises RuntimeError if any check fails.
    """
    logger.warning("Validating prerequisites...")

    # Check AWS CLI
    try:
        subprocess.run(
            ["aws", "--version"], capture_output=True, check=True
        )
        logger.info("  ✓ AWS CLI installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("AWS CLI is not installed. See: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html")

    # Check AWS SSO auth is valid
    try:
        identity = run_aws("sts get-caller-identity", region="us-east-1")
        account_id = identity["Account"]
        logger.info(f"  ✓ Authenticated to AWS account {account_id}")
    except RuntimeError:
        raise RuntimeError("AWS authentication failed. Run 'aws sso login' first.")

    # Ensure ECS service-linked role exists (required for first-time ECS usage)
    try:
        run_aws(
            "iam create-service-linked-role --aws-service-name ecs.amazonaws.com",
            region="us-east-1",
            quiet=True
        )
        logger.info("  ✓ ECS service-linked role created")
    except RuntimeError as err:
        if "already exists" in str(err) or "has been taken" in str(err):
            logger.info("  ✓ ECS service-linked role already exists (skipping — only needed once per account)")
        else:
            raise

    # Ensure Application Signals SLR exists (required for traces/metrics in CloudWatch)
    try:
        run_aws(
            "iam create-service-linked-role --aws-service-name application-signals.cloudwatch.amazonaws.com",
            region="us-east-1",
            quiet=True
        )
        logger.info("  ✓ Application Signals service-linked role created")
    except RuntimeError as err:
        if "already exists" in str(err) or "has been taken" in str(err):
            logger.info("  ✓ Application Signals service-linked role already exists (skipping — only needed once per account)")
        else:
            raise

    # Set account-level Container Insights to 'enhanced' (both regions).
    # This is idempotent — safe to run every deploy. It ensures new ECS clusters
    # default to enhanced observability (task + container level metrics).
    # The cluster-level setting in compute.yaml handles existing clusters.
    for region in ["us-east-1", "us-east-2"]:
        run_aws(
            "ecs put-account-setting --name containerInsights --value enhanced",
            region=region,
            quiet=True
        )
    logger.info("  ✓ Container Insights set to 'enhanced' (account-level, both regions)")


# ---------------------------------------------------------------------------
# Step 2: Collect deployment inputs interactively
# ---------------------------------------------------------------------------
def collect_inputs(args: argparse.Namespace) -> dict:
    """
    Prompt the operator for deployment configuration.
    CLI args override interactive prompts.

    Returns:
        Dict with all deployment configuration values.
    """
    # 'config' is a dict (dictionary) — Python's key-value data structure.
    # We build it up by either using CLI args or prompting the user.
    config = {}

    print("\n" + "=" * 60)
    print("  AirportHub Deployment Configuration")
    print("=" * 60 + "\n")

    # Fixed regions and prefix — AirportHub supports us-east-1 / us-east-2 only
    config["primary_region"] = "us-east-1"
    config["secondary_region"] = "us-east-2"
    config["stack_prefix"] = "airporthub"

    # FlightAware API key — collected upfront so deploy runs unattended
    if not getattr(args, 'teardown', False):
        import sys, tty, termios
        sys.stdout.write("\n  FlightAware API key (press Enter to skip): ")
        sys.stdout.flush()
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        fa_key = ""
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch in ("\r", "\n"):
                    break
                elif ch in ("\x7f", "\x08"):  # backspace
                    if fa_key:
                        fa_key = fa_key[:-1]
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                elif ch == "\x03":  # Ctrl+C
                    raise KeyboardInterrupt
                else:
                    fa_key += ch
                    sys.stdout.write("*")
                    sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print()  # newline after input
        config["flightaware_api_key"] = fa_key.strip()
        if not config["flightaware_api_key"]:
            print("  ⚠ No API key — scheduled refresh will be inactive")
    else:
        config["flightaware_api_key"] = ""

    # Derive stack names from prefix and region
    config["primary_stack"] = f"{config['stack_prefix']}-{config['primary_region']}"
    config["secondary_stack"] = f"{config['stack_prefix']}-{config['secondary_region']}"

    # Get AWS account ID for S3 bucket naming
    identity = run_aws("sts get-caller-identity", region=config["primary_region"])
    config["account_id"] = identity["Account"]

    # ARC approval role — prompt upfront so deploy runs unattended
    if not getattr(args, 'teardown', False) and not getattr(args, 'update_only', False):
        caller_arn = identity.get("Arn", "")
        if ":assumed-role/" in caller_arn:
            role_name = caller_arn.split("/")[-2]
            try:
                role_info = run_aws(f"iam get-role --role-name {role_name}", region=config["primary_region"])
                sso_role = role_info["Role"]["Arn"]
            except RuntimeError:
                parts = caller_arn.split(":")
                sso_role = f"arn:aws:iam::{parts[4]}:role/{role_name}"
        else:
            sso_role = caller_arn
        print(f"\n\033[36m  ─── ARC Region Switch - Approval Role ───\033[0m")
        print(f"")
        print(f"  ARC Region Switch uses human approval gates during DR failover.")
        print(f"  At each gate, an operator must:")
        print(f"")
        print(f"    1. Verify database health before compute scale-up")
        print(f"    2. Confirm application health before cleanup")
        print(f"")
        print(f"  The IAM role specified here determines who is authorized")
        print(f"  to approve at these gates.")
        print(f"")
        print(f"  \033[33mDetected SSO role:\033[0m")
        print(f"  {sso_role}")
        print(f"")
        approval_input = input(f"  Press Enter to accept, or provide a different role ARN: ").strip()
        config["approval_role"] = approval_input or sso_role
    else:
        config["approval_role"] = ""

    print(f"\n  Primary stack:   {config['primary_stack']}")
    print(f"  Secondary stack: {config['secondary_stack']}")
    print(f"  Account:         {config['account_id']}\n")

    return config


# ---------------------------------------------------------------------------
# Step 3: Install Lambda dependencies and package templates to S3
# ---------------------------------------------------------------------------
def install_lambda_dependencies() -> None:
    """Install pip dependencies into each Lambda directory for bundling."""
    lambda_dirs = [
        "airport-service",
        "crew-service",
        "flights-service",
        "custom-resources/data-seed",
        "scheduled-refresh-microservice",
    ]
    for lambda_dir in lambda_dirs:
        req_file = os.path.join(lambda_dir, "requirements.txt")
        if not os.path.isfile(req_file):
            continue
        logger.info(f"  Installing dependencies for {lambda_dir}...")
        result = subprocess.run(
            ["pip3", "install", "-r", req_file, "-t", lambda_dir, "--quiet", "--upgrade"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"pip install failed for {lambda_dir}: {result.stderr.strip()}")
    # Copy shared modules into Lambda directories that need them
    shutil.copy2("scheduled-refresh-microservice/flightaware_client.py", "flights-service/flightaware_client.py")
    logger.info("  Copied flightaware_client.py into flights-service/")
    # Copy DocumentDB TLS CA bundle into API Lambda directories
    for svc in ("airport-service", "crew-service", "flights-service"):
        shutil.copy2("data/global-bundle.pem", f"{svc}/global-bundle.pem")
    logger.info("  Copied global-bundle.pem into API Lambda directories")
    logger.warning("  ✅ Lambda dependencies installed")

    # Pre-flight validation — ensure all Lambda packages have required files
    required_files = {
        "airport-service": ["lambda_function.py", "auth.py", "global-bundle.pem"],
        "crew-service": ["lambda_function.py", "auth.py", "global-bundle.pem"],
        "flights-service": ["lambda_function.py", "auth.py", "global-bundle.pem", "flightaware_client.py", "flight_data_generator.py"],
        "custom-resources/data-seed": ["lambda_function.py", "global-bundle.pem"],
        "scheduled-refresh-microservice": ["lambda_function.py", "flightaware_client.py", "global-bundle.pem"],
    }
    missing = []
    for svc, files in required_files.items():
        for f in files:
            if not os.path.isfile(os.path.join(svc, f)):
                missing.append(f"{svc}/{f}")
    if missing:
        raise RuntimeError(f"Pre-flight check failed — missing files in Lambda packages:\n  " + "\n  ".join(missing))
    logger.info("  ✓ Pre-flight validation passed — all Lambda packages complete")


def package_templates(config: dict, region: str) -> str:
    """
    Create S3 bucket for templates and run 'aws cloudformation package'.

    Args:
        config: Deployment configuration dict
        region: Target AWS region

    Returns:
        Path to the packaged template file.
    """
    bucket_name = f"{config['stack_prefix']}-templates-{region}-{config['account_id']}"
    logger.warning(f"Packaging templates to s3://{bucket_name}")

    # Create bucket if it doesn't exist
    try:
        if region == "us-east-1":
            # us-east-1 doesn't accept LocationConstraint
            run_aws(f"s3api create-bucket --bucket {bucket_name}", region=region, quiet=True)
        else:
            run_aws(
                f"s3api create-bucket --bucket {bucket_name} "
                f"--create-bucket-configuration LocationConstraint={region}",
                region=region, quiet=True
            )
        logger.info(f"  Created S3 bucket: {bucket_name}")
    except RuntimeError as err:
        # BucketAlreadyOwnedByYou is fine — bucket already exists
        if "BucketAlreadyOwnedByYou" in str(err) or "already exists" in str(err):
            logger.info(f"  S3 bucket already exists: {bucket_name}")
        else:
            raise

    # Block public access on the template bucket
    run_aws(
        f"s3api put-public-access-block --bucket {bucket_name} "
        f"--public-access-block-configuration "
        f"BlockPublicAcls=true,IgnorePublicAcls=true,"
        f"BlockPublicPolicy=true,RestrictPublicBuckets=true",
        region=region
    )

    # Lifecycle rule: delete old packaged artifacts after 30 days (non-fatal if SCP blocks it)
    try:
        run_aws(
            f"s3api put-bucket-lifecycle-configuration --bucket {bucket_name} "
            f"--lifecycle-configuration "
            f"'{{\"Rules\":[{{\"ID\":\"expire-old-templates\",\"Status\":\"Enabled\","
            f"\"Expiration\":{{\"Days\":30}},\"Filter\":{{}}}}]}}'",
            region=region, quiet=True
        )
    except RuntimeError:
        logger.warning("  ⚠ Could not set lifecycle policy (SCP may block it) — skipping")

    # Package: uploads child templates to S3, rewrites TemplateURL references
    # Account-specific filename prevents collisions when deploying to multiple accounts from same workspace
    packaged_path = f"packaged-master-{region}-{config['account_id']}.yaml"
    package_cmd = (
        f"cloudformation package "
        f"--template-file airporthub-master.yaml "
        f"--s3-bucket {bucket_name} "
        f"--output-template-file {packaged_path}"
    )
    run_aws(package_cmd, region=region, capture=False)
    logger.info(f"  Packaged template: {packaged_path}")

    return packaged_path


# ---------------------------------------------------------------------------
# Step 4: Deploy master stack
# ---------------------------------------------------------------------------
def deploy_master_stack(
    config: dict,
    region: str,
    packaged_template: str,
    **override_params: str
) -> None:
    """
    Deploy the master nested stack to a region.

    Args:
        config: Deployment configuration dict
        region: Target AWS region
        packaged_template: Path to packaged template file
        **override_params: Additional parameter overrides for secondary region
    """
    stack_name = f"{config['stack_prefix']}-{region}"

    # Detect update vs create
    is_update = stack_exists(stack_name, region)
    action = "Updating existing" if is_update else "Creating new"
    logger.warning(f"{action} stack '{stack_name}' in {region}...")

    # Build parameter overrides — merge defaults with any overrides
    params = {
        "PrimaryRegion": config["primary_region"],
        "SecondaryRegion": config["secondary_region"],
        "StackPrefix": config["stack_prefix"],
        "VpcCidr": "10.0.0.0/16",
    }
    params.update(override_params)

    # Format as CloudFormation parameter overrides string
    param_overrides = " ".join(
        f"{key}={value}" for key, value in params.items()
    )

    deploy_cmd = (
        f"cloudformation deploy "
        f"--template-file {packaged_template} "
        f"--stack-name {stack_name} "
        f"--capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND "
        f"--parameter-overrides {param_overrides}"
    )
    run_aws(deploy_cmd, region=region, capture=False)
    logger.warning(f"  Stack '{stack_name}' deployed successfully")


# ---------------------------------------------------------------------------
# Step 5: Read stack outputs
# ---------------------------------------------------------------------------
def read_stack_outputs(stack_name: str, region: str) -> dict:
    """
    Read CloudFormation stack outputs into a key-value dict.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region

    Returns:
        Dict mapping output keys to values.
    """
    response = run_aws(
        f"cloudformation describe-stacks --stack-name {stack_name}",
        region=region
    )
    # 'Stacks' is a list; we want the first (and only) stack
    stacks = response.get("Stacks", [])
    if not stacks:
        raise RuntimeError(f"Stack '{stack_name}' not found in {region}")

    # Convert list of {OutputKey, OutputValue} dicts into a flat dict
    outputs = {}
    for output in stacks[0].get("Outputs", []):
        outputs[output["OutputKey"]] = output["OutputValue"]

    logger.info(f"  Read {len(outputs)} outputs from '{stack_name}'")
    return outputs


# ---------------------------------------------------------------------------
# Container build — upload source to S3, CodeBuild handles the rest
# ---------------------------------------------------------------------------
def upload_source_to_s3(config: dict, region: str) -> tuple:
    """
    Zip the application source and upload to S3 for CodeBuild.

    Returns:
        Tuple of (bucket_name, s3_key) for the uploaded source.
    """
    import zipfile
    import tempfile
    import os

    bucket_name = f"{config['stack_prefix']}-templates-{region}-{config['account_id']}"
    s3_key = "source/app-source.zip"

    logger.warning("Packaging application source for CodeBuild...")

    # Create a zip of the source directories needed for the Docker build
    # (app/, frontend/, data/global-bundle.pem, app/Dockerfile)
    source_dirs = ["app", "frontend", "data"]
    # Create a temp file path for the zip (fd closed immediately, path used by ZipFile)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    os.close(tmp_fd)

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src_dir in source_dirs:
            if not os.path.isdir(src_dir):
                continue
            for root, dirs, files in os.walk(src_dir):
                # Skip node_modules and __pycache__
                dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__", ".git", "dist")]
                for f in files:
                    filepath = os.path.join(root, f)
                    zf.write(filepath)

    # Upload to S3
    run_aws(
        f"s3 cp {tmp_path} s3://{bucket_name}/{s3_key}",
        region=region, capture=False
    )
    os.unlink(tmp_path)
    logger.info(f"  ✓ Source uploaded to s3://{bucket_name}/{s3_key}")

    return bucket_name, s3_key


def _update_flightaware_secret(config: dict) -> None:
    """Update the FlightAware API key in Secrets Manager (primary region only).

    Writes the key to the primary region secret. Secrets Manager replication
    automatically syncs to the secondary region - do not write to replicas directly.
    """
    import boto3
    secret_name = f"{config['stack_prefix']}/flightaware/api-key"
    secret_value = json.dumps({"api_key": config["flightaware_api_key"]})

    region = config["primary_region"]
    try:
        sm = boto3.client("secretsmanager", region_name=region)
        sm.put_secret_value(SecretId=secret_name, SecretString=secret_value)
        logger.info(f"  ✓ FlightAware secret updated in {region} (replicates to secondary)")
    except Exception as e:
        logger.warning(f"  ⚠ Could not update FA secret in {region}: {e}")


def force_ecs_deployment(config: dict, region: str) -> None:
    """
    Force a new ECS deployment to pick up the latest container image.
    """
    cluster = f"{config['stack_prefix']}-cluster"
    service = f"{config['stack_prefix']}-service"
    logger.warning(f"🔄 Forcing new ECS deployment: {cluster}/{service}")

    run_aws(
        f"ecs update-service --cluster {cluster} --service {service} --force-new-deployment --desired-count 2",
        region=region
    )
    logger.warning("  ✅ ECS deployment triggered")


def trigger_codebuild(config: dict, source_bucket: str, source_key: str) -> None:
    """
    Start a CodeBuild build and wait for it to complete.
    The CFN custom resource only triggers on CREATE — this ensures rebuilds on UPDATE too.
    """
    import time
    project = f"{config['stack_prefix']}-container-build"
    region = config["primary_region"]
    logger.warning(f"🔨 Triggering CodeBuild: {project}")

    resp = run_aws(
        f"codebuild start-build --project-name {project}"
        f" --environment-variables-override name=SOURCE_BUCKET,value={source_bucket} name=SOURCE_KEY,value={source_key}",
        region=region
    )
    build_id = resp["build"]["id"]
    logger.info(f"  Build started: {build_id}")

    # Poll until complete
    while True:
        time.sleep(15)  # nosemgrep: arbitrary-sleep
        builds = run_aws(f"codebuild batch-get-builds --ids {build_id}", region=region)
        status = builds["builds"][0]["buildStatus"]
        if status == "SUCCEEDED":
            logger.warning("  ✅ CodeBuild succeeded")
            return
        elif status == "IN_PROGRESS":
            logger.info(f"  ⏳ CodeBuild in progress...")
        else:
            raise RuntimeError(f"CodeBuild failed with status: {status}")


# ---------------------------------------------------------------------------
# Step 6: Wait for stack to reach a terminal state
# ---------------------------------------------------------------------------
def wait_for_stack(stack_name: str, region: str, timeout: int = 1800) -> str:
    """
    Poll stack status until it reaches a terminal state.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region
        timeout: Max seconds to wait (default 30 minutes)

    Returns:
        Final stack status string.
    """
    start = time.time()
    while time.time() - start < timeout:
        response = run_aws(
            f"cloudformation describe-stacks --stack-name {stack_name}",
            region=region
        )
        status = response["Stacks"][0]["StackStatus"]

        if status.endswith("_COMPLETE") or status.endswith("_FAILED"):
            logger.info(f"  Stack '{stack_name}' status: {status}")
            return status

        logger.info(f"  Waiting... {stack_name} status: {status}")
        time.sleep(15)  # nosemgrep: arbitrary-sleep

    raise RuntimeError(f"Timeout waiting for stack '{stack_name}' after {timeout}s")


# ---------------------------------------------------------------------------
# Teardown — full cleanup of all AirportHub resources
# ---------------------------------------------------------------------------
def teardown_all(config: dict) -> None:
    """
    Remove all AirportHub resources from both regions.

    Deletion order matters — child plans before parent, secondary before primary,
    S3 emptied before stack deletion.
    """
    print("\n" + "=" * 60)
    print("  🚨 AirportHub TEARDOWN")
    print("=" * 60)
    print(f"\n  This will DELETE all resources in:")
    print(f"    Primary:   {config['primary_stack']} ({config['primary_region']})")
    print(f"    Secondary: {config['secondary_stack']} ({config['secondary_region']})")
    print(f"    ARC Plan:  {config['stack_prefix']}-arc-plan")
    print(f"    FlightAware: flightaware-app-switchover (both regions)\n")

    confirm = input("  Type 'yes' to confirm teardown: ").strip()
    if confirm.lower() != "yes":
        logger.info("Teardown cancelled. No resources were deleted.")
        return

    print(f"\n  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  🗑️  Confirmed. Deleting all AirportHub resources from account {config['account_id']}")
    print(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Press Ctrl+C to abort.\n")

    # Teardown steps: 11 total
    # FlightAware x2, ARC plan, ECR x2, secondary stack, primary stack, S3 x2, logs x2
    TEARDOWN_STEPS = 11
    progress = create_progress_bar()

    if progress:
        with progress:
            task = progress.add_task("Tearing down AirportHub", total=TEARDOWN_STEPS)

            # Steps 1-2: Delete FlightAware stacks (both regions)
            for i, region in enumerate([config["primary_region"], config["secondary_region"]], start=1):
                progress.update(task, description=f"[{i}/11] Deleting FlightAware ({region})")
                _delete_stack_safe(f"flightaware-app-switchover-{region}", region)
                progress.advance(task)
                step_done(f"FlightAware gone from {region} — scheduled refresh decommissioned")

            # Step 3: Delete ARC plan stack
            progress.update(task, description="[3/11] Deleting ARC plan")
            _empty_and_delete_bucket(f"{config['stack_prefix']}-arc-reports-{config['account_id']}", config["primary_region"])
            _delete_stack_safe(f"{config['stack_prefix']}-arc-plan", config["primary_region"])
            progress.advance(task)
            step_done("ARC recovery plan removed — failover automation retired")

            # Steps 4-5: Clean ECR repos
            for i, region in enumerate([config["primary_region"], config["secondary_region"]], start=4):
                progress.update(task, description=f"[{i}/11] Deleting ECR repo ({region})")
                _delete_ecr_repo(f"{config['stack_prefix']}-app", region)
                progress.advance(task)
                step_done(f"Container images wiped from ECR in {region}")

            # Step 6: Delete secondary master stack
            progress.update(task, description="[6/11] Deleting secondary stack (us-east-2)")
            _delete_stack_safe(config["secondary_stack"], config["secondary_region"])
            progress.advance(task)
            step_done("Secondary region torn down — pilot light extinguished")

            # Step 7: Delete primary master stack
            progress.update(task, description="[7/11] Deleting primary stack (us-east-1)")
            _delete_stack_safe(config["primary_stack"], config["primary_region"])
            progress.advance(task)
            step_done("Primary region torn down — all compute and database resources deleted")

            # Steps 8-9: Empty and delete S3 template buckets
            for i, region in enumerate([config["primary_region"], config["secondary_region"]], start=8):
                bucket = f"{config['stack_prefix']}-templates-{region}-{config['account_id']}"
                progress.update(task, description=f"[{i}/11] Deleting S3 bucket ({region})")
                _empty_and_delete_bucket(bucket, region)
                progress.advance(task)
                step_done(f"Template bucket emptied and deleted in {region}")

            # Steps 10-11: Delete CloudWatch log groups
            for i, region in enumerate([config["primary_region"], config["secondary_region"]], start=10):
                progress.update(task, description=f"[{i}/11] Deleting log groups ({region})")
                _delete_log_groups(config["stack_prefix"], region)
                progress.advance(task)
                step_done(f"CloudWatch log groups purged in {region} — no traces left")

            progress.update(task, description="[bold green]Teardown complete!")

    else:
        # Fallback: no rich — same logic with logger output
        _run_teardown_steps(config)

    logger.warning("\nTeardown complete — all resources removed.")


def _delete_stack_safe(stack_name: str, region: str) -> None:
    """Delete a CloudFormation stack, ignoring if it doesn't exist.
    
    Retries once after 60s if delete fails (handles VPC Origin ENI drain timeout).
    """
    try:
        logger.info(f"Deleting stack: {stack_name} ({region})")
        run_aws(f"cloudformation delete-stack --stack-name {stack_name}", region=region)
        run_aws(
            f"cloudformation wait stack-delete-complete --stack-name {stack_name}",
            region=region, capture=False
        )
        logger.info(f"  ✓ Deleted {stack_name}")
    except RuntimeError as err:
        if "does not exist" in str(err) or "ValidationError" in str(err):
            logger.info(f"  ⏭ Stack {stack_name} not found — skipping")
        else:
            # Retry once — VPC Origin ENIs take 5-10 min to release, causing DELETE_FAILED
            logger.warning(f"  ⚠ Delete failed for {stack_name}, retrying in 60s (VPC Origin ENI drain)...")
            time.sleep(60)
            try:
                run_aws(f"cloudformation delete-stack --stack-name {stack_name}", region=region)
                run_aws(
                    f"cloudformation wait stack-delete-complete --stack-name {stack_name}",
                    region=region, capture=False
                )
                logger.info(f"  ✓ Deleted {stack_name} (retry succeeded)")
            except RuntimeError as retry_err:
                logger.warning(f"  ⚠ Retry also failed for {stack_name}: {retry_err}")


def _empty_and_delete_bucket(bucket: str, region: str) -> None:
    """Empty an S3 bucket then delete it."""
    try:
        logger.info(f"Emptying bucket: {bucket}")
        run_aws(f"s3 rm s3://{bucket} --recursive", region=region, capture=False)
        run_aws(f"s3api delete-bucket --bucket {bucket}", region=region)
        logger.info(f"  ✓ Deleted bucket {bucket}")
    except RuntimeError:
        logger.info(f"  ⏭ Bucket {bucket} not found — skipping")


def _delete_ecr_repo(repo_name: str, region: str) -> None:
    """Delete an ECR repository and all images."""
    try:
        run_aws(
            f"ecr delete-repository --repository-name {repo_name} --force",
            region=region
        )
        logger.info(f"  ✓ Deleted ECR repo {repo_name} ({region})")
    except RuntimeError:
        logger.info(f"  ⏭ ECR repo {repo_name} not found in {region} — skipping")


def _delete_log_groups(prefix: str, region: str) -> None:
    """Delete CloudWatch log groups matching the stack prefix."""
    try:
        response = run_aws(
            f"logs describe-log-groups --log-group-name-prefix /ecs/{prefix}",
            region=region
        )
        for group in response.get("logGroups", []):
            name = group["logGroupName"]
            run_aws(f"logs delete-log-group --log-group-name {name}", region=region)
            logger.info(f"  ✓ Deleted log group {name}")

        # Also delete Lambda log groups
        response = run_aws(
            f"logs describe-log-groups --log-group-name-prefix /aws/lambda/{prefix}",
            region=region
        )
        for group in response.get("logGroups", []):
            name = group["logGroupName"]
            run_aws(f"logs delete-log-group --log-group-name {name}", region=region)
            logger.info(f"  ✓ Deleted log group {name}")
    except RuntimeError:
        logger.info(f"  ⏭ No log groups found for {prefix} in {region}")


# ---------------------------------------------------------------------------
# Deploy ARC plan and FlightAware microservice
# ---------------------------------------------------------------------------
def deploy_arc_plan(config: dict, primary_outputs: dict, secondary_outputs: dict, approval_role: str) -> None:
    """
    Deploy the ARC parent plan stack with resource ARNs from both regions.

    The ARC plan references ECS, ALB, DocDB, CloudFront, and Lambda ARNs
    from both regions to orchestrate failover.
    """
    stack_name = f"{config['stack_prefix']}-arc-plan"
    logger.warning(f"🛡️ Deploying ARC plan: {stack_name}")

    # Read the FlightAware child plan ARN from the primary region's switchover stack
    flightaware_stack = f"flightaware-app-switchover-{config['primary_region']}"
    try:
        fa_outputs = read_stack_outputs(flightaware_stack, config["primary_region"])
        child_plan_arn = fa_outputs.get("ChildPlanArn", "")
    except RuntimeError:
        logger.warning("  ⚠ FlightAware child plan ARN not found — ARC plan will skip nested plan")
        child_plan_arn = ""

    param_overrides = " ".join([
        f"StackPrefix={config['stack_prefix']}",
        f"PrimaryRegion={config['primary_region']}",
        f"SecondaryRegion={config['secondary_region']}",
        f"PrimaryEcsClusterArn={primary_outputs.get('EcsClusterArn', '')}",
        f"PrimaryEcsServiceArn={primary_outputs.get('EcsServiceArn', '')}",
        f"PrimaryAlbArn={primary_outputs.get('AlbArn', '')}",
        f"SecondaryEcsClusterArn={secondary_outputs.get('EcsClusterArn', '')}",
        f"SecondaryEcsServiceArn={secondary_outputs.get('EcsServiceArn', '')}",
        f"SecondaryAlbArn={secondary_outputs.get('AlbArn', '')}",
        f"CloudFrontDistributionId={primary_outputs.get('CloudFrontDistributionId', '')}",
        f"PrimaryAlbDnsName={primary_outputs.get('AlbDnsName', '')}",
        f"SecondaryAlbDnsName={secondary_outputs.get('AlbDnsName', '')}",
        f"DocDbGlobalClusterIdentifier={primary_outputs.get('GlobalClusterIdentifier', '')}",
        f"PrimaryDocDbClusterIdentifier={primary_outputs.get('ClusterIdentifier', '')}",
        f"SecondaryDocDbClusterIdentifier={secondary_outputs.get('ClusterIdentifier', '')}",
        f"PrimaryFlightsLambdaArn={primary_outputs.get('FlightsLambdaArn', '')}",
        f"SecondaryFlightsLambdaArn={secondary_outputs.get('FlightsLambdaArn', '')}",
        f"FlightAwareChildPlanArn={child_plan_arn}",
        f"ApprovalRoleArn={approval_role}",
        f"PrimaryCfSwitchFunctionArn={primary_outputs.get('CfSwitchFunctionArn', '')}",
        f"SecondaryCfSwitchFunctionArn={secondary_outputs.get('CfSwitchFunctionArn', '')}",
        f"PrimaryEcsScaleDownFunctionArn={primary_outputs.get('EcsScaleDownFunctionArn', '')}",
        f"SecondaryEcsScaleDownFunctionArn={secondary_outputs.get('EcsScaleDownFunctionArn', '')}",
    ])

    deploy_cmd = (
        f"cloudformation deploy "
        f"--template-file infrastructure/arc-region-switch-plan.yaml "
        f"--stack-name {stack_name} "
        f"--capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM "
        f"--parameter-overrides {param_overrides}"
    )
    run_aws(deploy_cmd, region=config["primary_region"], capture=False)
    logger.warning("  ✅ ARC plan deployed")


def deploy_flightaware(config: dict, primary_outputs: dict, secondary_outputs: dict, approval_role: str) -> None:
    """Deploy the FlightAware microservice to both regions (in parallel)."""
    import concurrent.futures

    regions_outputs = {
        config["primary_region"]: primary_outputs,
        config["secondary_region"]: secondary_outputs,
    }

    def _deploy_fa_region(region: str) -> str:
        outputs = regions_outputs[region]
        stack_name = f"flightaware-app-switchover-{region}"
        schedule_state = "ENABLED" if region == config["primary_region"] else "DISABLED"
        bucket = f"{config['stack_prefix']}-templates-{region}-{config['account_id']}"

        params = " ".join([
            f"DocDBEndpoint={outputs.get('ClusterEndpoint', '')}",
            f"DocDBSecretArn={outputs.get('SecretArn', '')}",
            f"VpcId={outputs.get('VpcId', '')}",
            f"PrivateSubnet1={outputs.get('PrivateSubnet1Id', '')}",
            f"PrivateSubnet2={outputs.get('PrivateSubnet2Id', '')}",
            f"DocDBSecurityGroupId={outputs.get('LambdaSecurityGroupId', '')}",
            f"ScheduleState={schedule_state}",
            f"PrimaryRegion={config['primary_region']}",
            f"SecondaryRegion={config['secondary_region']}",
            f"ApprovalRoleArn={approval_role}",
        ])

        packaged_path = f"packaged-flightaware-{region}-{config['account_id']}.yaml"
        package_cmd = (
            f"cloudformation package "
            f"--template-file scheduled-refresh-microservice/flightaware-app-switchover.yaml "
            f"--s3-bucket {bucket} "
            f"--output-template-file {packaged_path}"
        )
        deploy_cmd = (
            f"cloudformation deploy "
            f"--template-file {packaged_path} "
            f"--stack-name {stack_name} "
            f"--capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM "
            f"--parameter-overrides {params}"
        )
        run_aws(package_cmd, region=region, capture=False)
        run_aws(deploy_cmd, region=region, capture=False)
        return region

    logger.warning("Deploying FlightAware microservice to both regions (parallel)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(_deploy_fa_region, r): r for r in [config["primary_region"], config["secondary_region"]]}
        for future in concurrent.futures.as_completed(futures):
            region = futures[future]
            try:
                future.result()
                logger.warning(f"  ✅ FlightAware deployed to {region}")
            except Exception as err:
                raise RuntimeError(f"FlightAware deploy to {region} failed: {err}")


def print_summary(config: dict, primary_outputs: dict) -> None:
    """Print deployment summary with URLs, stack details, resource counts, and cost estimate."""
    cf_domain = primary_outputs.get("CloudFrontDomainName", "N/A")
    cognito_pool = primary_outputs.get("CognitoUserPoolId", "N/A")
    dashboard_url = primary_outputs.get("DashboardUrl", "N/A")

    # --- Print ---
    print("\n" + "=" * 60)
    print("  ✅ AirportHub Deployment Complete!")
    print("=" * 60)
    print(f"\n  🌐 Application URL:  https://{cf_domain}")
    print(f"  🔐 Cognito Pool ID:  {cognito_pool}")
    print(f"  📊 Dashboard:        {dashboard_url}")
    print(f"  🏢 AWS Account:      {config.get('account_id', 'N/A')}")
    print(f"\n  Primary Region:      {config['primary_region']}")
    print(f"  Secondary Region:    {config['secondary_region']}")

    region = config['primary_region']
    print(f"\n  Next steps:")
    print(f"    1. Create your first user:")
    print(f"       → Open https://{region}.console.aws.amazon.com/cognito/v2/idp/user-pools/{cognito_pool}/users?region={region}")
    print(f"       → Click 'Create user'")
    print(f"       → Enter email, set a temporary password, and click 'Create user'")
    print(f"       → Sign in at https://{cf_domain}/login with the temporary password")
    print(f"       → You'll be prompted to set a permanent password on first login")
    print(f"    2. Check the CloudWatch dashboard for metrics")
    print(f"    3. Test DR failover via ARC console")
    print(f"\n  To teardown: python deploy.py --teardown")
    print("=" * 60 + "\n")


def _run_full_deploy(config: dict) -> None:
    """Execute the full deploy sequence (shared logic for rich and non-rich paths)."""
    import concurrent.futures

    install_lambda_dependencies()
    step_done("Lambda packages bundled and ready to ship")

    # Package BOTH region templates in parallel (they're independent)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_primary = executor.submit(package_templates, config, config["primary_region"])
        future_secondary = executor.submit(package_templates, config, config["secondary_region"])
        packaged = future_primary.result()
        packaged_secondary = future_secondary.result()
    step_done("Templates packaged for both regions (parallel)")

    source_bucket, source_key = upload_source_to_s3(config, config["primary_region"])
    step_done("Application source staged for CodeBuild")

    container_image = f"{config['account_id']}.dkr.ecr.{config['primary_region']}.amazonaws.com/{config['stack_prefix']}-app:latest"
    deploy_master_stack(
        config, config["primary_region"], packaged,
        SourceBucket=source_bucket, SourceKey=source_key, ContainerImageUri=container_image,
    )
    primary_outputs = read_stack_outputs(config["primary_stack"], config["primary_region"])
    step_done("Primary region live")
    logger.warning("Primary region deployment complete!")

    if config.get("flightaware_api_key"):
        _update_flightaware_secret(config)
        config["flightaware_api_key"] = ""

    # Run CodeBuild AND secondary stack deploy in parallel
    # Secondary doesn't need the container image — it runs 0 ECS tasks (pilot light)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        def _codebuild_and_ecs():
            trigger_codebuild(config, source_bucket, source_key)
            force_ecs_deployment(config, config["primary_region"])

        def _deploy_secondary():
            deploy_master_stack(
                config, config["secondary_region"], packaged_secondary,
                CognitoUserPoolId=primary_outputs.get("CognitoUserPoolId", ""),
                CognitoUserPoolArn=primary_outputs.get("CognitoUserPoolArn", ""),
                CognitoAppClientId=primary_outputs.get("CognitoAppClientId", ""),
                GlobalClusterIdentifier=primary_outputs.get("GlobalClusterIdentifier", ""),
                ContainerImageUri=container_image,
            )

        future_build = executor.submit(_codebuild_and_ecs)
        future_secondary = executor.submit(_deploy_secondary)

        # Wait for both and raise any errors
        future_build.result()
        step_done("Container image built + ECS rolling out")
        future_secondary.result()

    secondary_outputs = read_stack_outputs(config["secondary_stack"], config["secondary_region"])
    step_done("Secondary region standing by")
    logger.warning("Secondary region deployment complete!")

    approval_role = config["approval_role"]
    deploy_flightaware(config, primary_outputs, secondary_outputs, approval_role)
    step_done("FlightAware microservice deployed")

    deploy_arc_plan(config, primary_outputs, secondary_outputs, approval_role)
    step_done("ARC Region Switch plan armed")


def _run_teardown_steps(config: dict) -> None:
    """Execute the full teardown sequence (shared logic for rich and non-rich paths)."""
    for region in [config["primary_region"], config["secondary_region"]]:
        _delete_stack_safe(f"flightaware-app-switchover-{region}", region)
        step_done(f"FlightAware gone from {region}")

    _empty_and_delete_bucket(f"{config['stack_prefix']}-arc-reports-{config['account_id']}", config["primary_region"])
    _delete_stack_safe(f"{config['stack_prefix']}-arc-plan", config["primary_region"])
    step_done("ARC plan removed")

    for region in [config["primary_region"], config["secondary_region"]]:
        _delete_ecr_repo(f"{config['stack_prefix']}-app", region)
        step_done(f"ECR repo deleted in {region}")

    _delete_stack_safe(config["secondary_stack"], config["secondary_region"])
    step_done("Secondary region torn down")

    _delete_stack_safe(config["primary_stack"], config["primary_region"])
    step_done("Primary region torn down")

    for region in [config["primary_region"], config["secondary_region"]]:
        bucket = f"{config['stack_prefix']}-templates-{region}-{config['account_id']}"
        _empty_and_delete_bucket(bucket, region)
        step_done(f"Template bucket deleted in {region}")

    for region in [config["primary_region"], config["secondary_region"]]:
        _delete_log_groups(config["stack_prefix"], region)
        step_done(f"Log groups purged in {region}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """
    CLI entry point — parse args and run deploy or teardown.

    argparse is Python's built-in module for parsing command-line arguments.
    We define flags like --teardown, --stack-prefix, etc.
    """
    parser = argparse.ArgumentParser(
        description="AirportHub — guided deployment and teardown"
    )
    parser.add_argument(
        "--teardown", action="store_true",
        help="Teardown all AirportHub resources"
    )
    parser.add_argument(
        "--update-only", action="store_true",
        help="Fast update: refresh FlightAware API key & rebuild container and redeploy ECS only (skips CFN stack updates)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Package templates and show change sets without deploying"
    )
    parser.add_argument("--profile", default=None, help="AWS CLI profile name")

    args = parser.parse_args()

    # Set the global profile so every run_aws() call includes --profile
    global AWS_PROFILE
    AWS_PROFILE = args.profile

    try:
        validate_prerequisites()

        if args.teardown:
            config = collect_inputs(args)
            teardown_all(config)
            return

        config = collect_inputs(args)

        # --- Fast update mode: rebuild container + redeploy ECS only ---
        if args.update_only:
            logger.warning("⚡ Update-only mode — refreshing API key, rebuilding container, hot-swapping ECS (no CFN, no waiting)")
            source_bucket, source_key = upload_source_to_s3(config, config["primary_region"])
            step_done("Application source uploaded to S3")

            trigger_codebuild(config, source_bucket, source_key)
            step_done("Container image built and pushed to ECR")

            force_ecs_deployment(config, config["primary_region"])
            step_done("ECS service rolling out fresh containers")

            primary_outputs = read_stack_outputs(config["primary_stack"], config["primary_region"])
            print_summary(config, primary_outputs)
            return

        # --- Dry-run mode: package templates and show change sets ---
        if args.dry_run:
            logger.warning("🔍 Dry-run mode — packaging templates and creating change sets")
            install_lambda_dependencies()
            step_done("Lambda dependencies installed")

            packaged = package_templates(config, config["primary_region"])
            step_done(f"Primary templates packaged: {packaged}")

            # Create change set without executing
            stack_name = config["primary_stack"]
            container_image = f"{config['account_id']}.dkr.ecr.{config['primary_region']}.amazonaws.com/{config['stack_prefix']}-app:latest"
            params = " ".join([
                f"PrimaryRegion={config['primary_region']}",
                f"SecondaryRegion={config['secondary_region']}",
                f"StackPrefix={config['stack_prefix']}",
                f"VpcCidr=10.0.0.0/16",
                f"ContainerImageUri={container_image}",
            ])
            cs_name = f"dry-run-{int(time.time())}"
            cs_type = "UPDATE" if stack_exists(stack_name, config["primary_region"]) else "CREATE"
            try:
                run_aws(
                    f"cloudformation create-change-set "
                    f"--stack-name {stack_name} "
                    f"--change-set-name {cs_name} "
                    f"--change-set-type {cs_type} "
                    f"--template-body file://{packaged} "
                    f"--capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND "
                    f"--parameter-overrides {params}",
                    region=config["primary_region"]
                )
                # Wait for change set to be created
                time.sleep(5)  # nosemgrep: arbitrary-sleep
                cs = run_aws(
                    f"cloudformation describe-change-set --stack-name {stack_name} --change-set-name {cs_name}",
                    region=config["primary_region"]
                )
                print("\n" + "=" * 60)
                print(f"  Change Set: {cs_name} ({cs_type})")
                print("=" * 60)
                changes = cs.get("Changes", [])
                if not changes:
                    print("  No changes detected.")
                else:
                    print(f"  {len(changes)} resource(s) affected:\n")
                    for c in changes[:20]:
                        rc = c.get("ResourceChange", {})
                        print(f"    {rc.get('Action', '?'):8s} {rc.get('ResourceType', ''):40s} {rc.get('LogicalResourceId', '')}")
                print("\n  Change set NOT executed (dry-run). Delete with:")
                print(f"  aws cloudformation delete-change-set --stack-name {stack_name} --change-set-name {cs_name} --region {config['primary_region']}")
                print("=" * 60 + "\n")
            except RuntimeError as err:
                logger.warning(f"  Could not create change set: {err}")
            return

        # --- Show deployment plan and get confirmation ---
        show_deployment_plan(config)

        # --- Deploy with progress tracking ---
        # Weighted steps — values approximate relative duration of each step
        # (Lambda deps: 5s, packaging both: 15s, source upload: 5s, primary stack: 600s,
        #  CodeBuild+secondary parallel: 900s, FlightAware: 60s, ARC plan: 30s, finalize: 5s)
        STEP_WEIGHTS = [5, 15, 5, 600, 900, 60, 30, 5]
        TOTAL_WEIGHT = sum(STEP_WEIGHTS)
        progress = create_progress_bar()

        if progress:
            import concurrent.futures
            # Use progress bar as a context manager — it renders in the terminal
            # and allows log output to appear above the bar
            with progress:
                task = progress.add_task("Deploying AirportHub", total=TOTAL_WEIGHT)

                # Step 1: Install Lambda dependencies
                progress.update(task, description="[1/8] Installing Lambda dependencies")
                install_lambda_dependencies()
                progress.advance(task, STEP_WEIGHTS[0])
                step_done("Lambda packages bundled and ready to ship")

                # Step 2: Package BOTH region templates in parallel
                progress.update(task, description="[2/8] Packaging templates (both regions)")
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_primary = executor.submit(package_templates, config, config["primary_region"])
                    future_secondary = executor.submit(package_templates, config, config["secondary_region"])
                    packaged = future_primary.result()
                    packaged_secondary = future_secondary.result()
                progress.advance(task, STEP_WEIGHTS[1])
                step_done("Templates packaged for both regions (parallel)")

                # Step 3: Upload source for CodeBuild
                progress.update(task, description="[3/8] Uploading source to S3")
                source_bucket, source_key = upload_source_to_s3(
                    config, config["primary_region"]
                )
                progress.advance(task, STEP_WEIGHTS[2])
                step_done("Application source zipped and staged for CodeBuild")

                # Step 4: Deploy primary master stack
                container_image = f"{config['account_id']}.dkr.ecr.{config['primary_region']}.amazonaws.com/{config['stack_prefix']}-app:latest"
                progress.update(task, description="[4/8] Deploying primary stack (us-east-1)")
                deploy_master_stack(
                    config, config["primary_region"], packaged,
                    SourceBucket=source_bucket,
                    SourceKey=source_key,
                    ContainerImageUri=container_image,
                )
                primary_outputs = read_stack_outputs(
                    config["primary_stack"], config["primary_region"]
                )
                progress.advance(task, STEP_WEIGHTS[3])
                step_done("Primary region live — VPC, Auth, Database, Compute, API all up")

                logger.warning("Primary region deployment complete!")

                # Update FlightAware secret (if key provided upfront)
                if config.get("flightaware_api_key"):
                    _update_flightaware_secret(config)
                    config["flightaware_api_key"] = ""

                # Step 5: CodeBuild + Secondary stack IN PARALLEL
                # Secondary doesn't need container image — it runs 0 ECS tasks (pilot light)
                progress.update(task, description="[5/8] CodeBuild + Secondary stack (parallel)")

                def _codebuild_and_ecs():
                    trigger_codebuild(config, source_bucket, source_key)
                    force_ecs_deployment(config, config["primary_region"])

                def _deploy_secondary():
                    deploy_master_stack(
                        config, config["secondary_region"], packaged_secondary,
                        CognitoUserPoolId=primary_outputs.get("CognitoUserPoolId", ""),
                        CognitoUserPoolArn=primary_outputs.get("CognitoUserPoolArn", ""),
                        CognitoAppClientId=primary_outputs.get("CognitoAppClientId", ""),
                        GlobalClusterIdentifier=primary_outputs.get("GlobalClusterIdentifier", ""),
                        ContainerImageUri=container_image,
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_build = executor.submit(_codebuild_and_ecs)
                    future_sec = executor.submit(_deploy_secondary)
                    future_build.result()
                    future_sec.result()

                secondary_outputs = read_stack_outputs(
                    config["secondary_stack"], config["secondary_region"]
                )
                progress.advance(task, STEP_WEIGHTS[4])
                step_done("Container built + Secondary region standing by (parallel)")

                logger.warning("Secondary region deployment complete!")

                # --- Pause progress for ARC deployment ---
                progress.update(task, description="[6/8] Deploying FlightAware + ARC")
                progress.stop()

            # Use approval role collected upfront
            approval_role = config["approval_role"]

            # --- Resume progress bar for final steps ---
            with progress:
                progress.start()
                # Step 6: Deploy FlightAware
                progress.update(task, description="[6/8] Deploying FlightAware (both regions)")
                deploy_flightaware(config, primary_outputs, secondary_outputs, approval_role)
                progress.advance(task, STEP_WEIGHTS[5])
                step_done("FlightAware microservice deployed — scheduled refresh active")

                # Step 7: Deploy ARC plan
                progress.update(task, description="[7/8] Deploying ARC plan")
                deploy_arc_plan(config, primary_outputs, secondary_outputs, approval_role)
                progress.advance(task, STEP_WEIGHTS[6])
                step_done("ARC Region Switch plan armed — DR failover ready")

                # Step 8: Read final outputs
                progress.update(task, description="[8/8] Finalizing deployment")
                primary_outputs = read_stack_outputs(
                    config["primary_stack"], config["primary_region"]
                )
                progress.advance(task, STEP_WEIGHTS[7])
                step_done(f"Multi-Region Sample Application (AirportHub) is live across both regions in AWS account {config['account_id']}")

                progress.update(task, description="[bold green]Deployment complete!")

        else:
            # Fallback: no rich installed — same logic, logger-based output
            _run_full_deploy(config)

        # Print final summary (outside progress bar for clean output)
        primary_outputs = read_stack_outputs(config["primary_stack"], config["primary_region"])
        print_summary(config, primary_outputs)

        # Clean up temporary packaged template files
        import glob
        for f in glob.glob(os.path.join(os.path.dirname(__file__), "packaged-*.yaml")):
            os.remove(f)

    except RuntimeError as err:
        logger.error(f"Deployment failed: {err}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nDeployment cancelled by user.")
        sys.exit(1)


# This guard ensures main() only runs when the script is executed directly,
# not when it's imported as a module by another script.
if __name__ == "__main__":
    main()

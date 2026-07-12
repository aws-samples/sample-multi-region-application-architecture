# Failover Operations Runbook — ARC Region Switch

This is the **operator runbook** for executing and managing ARC Region Switch failovers for the AirportHub application. For architecture context, design decisions, and the full project overview, see the [main README](../README.md).

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [How to Start a Failover](#how-to-start-a-failover)
3. [Plan Steps and Timeouts](#plan-steps-and-timeouts)
4. [Approving Manual Gates](#approving-manual-gates)
5. [How CloudFront Failover Works](#how-cloudfront-failover-works)
6. [Execution Reports](#execution-reports)
7. [References](#references)

---

## Quick Reference

| | |
|---|---|
| **DR Pattern** | Pilot Light (Active/Passive) |
| **Primary Region** | us-east-1 (N. Virginia) |
| **Recovery Region** | us-east-2 (Ohio) |
| **RTO Target** | 15 minutes |
| **RPO Target** | Near-zero (DocumentDB Global Cluster continuous replication) |
| **Trigger** | Manual — operator-initiated from ARC console or CLI |
| **Plan Name** | `airporthub-region-switch` |
| **Execution Reports** | S3 bucket: `airporthub-arc-reports-<ACCOUNT_ID>` |

---

## How to Start a Failover

### From the AWS Console

1. In the AWS Console, **navigate to the Region you want to activate** (us-east-2 for failover, us-east-1 for failback)
2. Open **Application Recovery Controller** > **Region switch**
3. Select the `airporthub-region-switch` plan
4. Choose **Execute plan**
5. Approve manual steps as they come up (see [Approving Manual Gates](#approving-manual-gates))

### From the CLI

```bash
aws arc-region-switch start-plan-execution \
  --plan-arn <PLAN_ARN> \
  --target-region us-east-2
```

> [!NOTE]
> The plan ARN is output by the `airporthub-arc-plan` CloudFormation stack. Retrieve it with:
> ```bash
> aws cloudformation describe-stacks \
>   --stack-name airporthub-arc-plan \
>   --query 'Stacks[0].Outputs[?OutputKey==`PlanArn`].OutputValue' \
>   --output text
> ```

---

## Plan Steps and Timeouts

Both failover and failback follow a symmetric 6-step structure. The plan orchestrates dependency ordering — DocumentDB switches before compute activates, with human approval gates between stages.

| Step | Action | Timeout | Notes |
|---|---|---|---|
| 1 | DocumentDB Global Cluster Switchover | 10 min | `switchoverOnly` behavior (zero data loss); ungraceful failover option available |
| 2 | Seed Live Flight Data (FlightAware Lambda) | 5 min | Runs in activating region; 5 min retry interval |
| 3 | **Manual Approval** | See below | Operator confirms DB + data health |
| 4 | ECS Scale Up (target region) | 10 min | Uses `sampledMaxInLast24Hours` at 100% capacity |
| 5 | **Manual Approval** | See below | Operator confirms application health |
| 6 | Parallel: FlightAware Child Plan + Scale Down Source ECS | 60 min | Skipped on ungraceful failover |

### Approval Timeout Differences

> [!IMPORTANT]
> Failover and failback have **different** approval timeouts. Failback allows more time because operators may need to validate data consistency after switching back.

| Approval Gate | Failover (activate us-east-2) | Failback (activate us-east-1) |
|---|---|---|
| Step 3 | 10 min | **20 min** |
| Step 5 | 10 min | **20 min** |

### Step Names by Direction

| Step | Failover (activate us-east-2) | Failback (activate us-east-1) |
|---|---|---|
| 3 | `FailoverApproval` | `FailbackApproval` |
| 5 | `FinalApproval` | `FinalApprovalFailback` |

### Step 6 — Parallel Cleanup

Step 6 runs two actions in parallel:

1. **FlightAware Child Plan** (`flightaware-app-switchover`) — a nested ARC plan that enables the EventBridge schedule in the target region and disables it in the source region
2. **Scale Down Source ECS** — a custom Lambda that sets the source region ECS desired count to 0, returning it to Pilot Light state

> [!NOTE]
> Step 6 is **skipped on ungraceful failover**. If the source region is unavailable, the schedule disable and ECS scale-down cannot execute. You must clean these up manually once the source region recovers.

---

## Approving Manual Gates

Steps 3 and 5 pause execution and wait for an authorized operator to approve.

### Who Can Approve

The operator must be signed in with the IAM role specified as `ApprovalRoleArn` during deployment.

> [!WARNING]
> For SSO roles, the **full IAM path** is required. Using a short ARN causes `AccessDeniedException`.

```bash
# Get your role's full ARN (including IAM path)
aws sts get-caller-identity
# → arn:aws:sts::ACCOUNT:assumed-role/ROLE_NAME/session

aws iam get-role --role-name ROLE_NAME --query 'Role.Arn'
# → arn:aws:iam::ACCOUNT:role/aws-reserved/sso.amazonaws.com/ROLE_NAME
```

### Console Walkthrough

1. In **Application Recovery Controller** > **Region switch**, select the `airporthub-region-switch` plan
2. Click the active **Execution ID** in the Executions section
3. The step with a **Pending approval** badge is waiting for you
4. Click the pending step, review preceding results, then choose **Approve** or **Decline**
5. Execution resumes automatically within seconds of approval

### What to Verify Before Step 3 Approval

- [ ] DocumentDB switchover completed — DocumentDB console in target region shows cluster role as **Writer**
- [ ] Flight data seed Lambda (Step 2) shows **Succeeded** in the execution timeline
- [ ] Secrets Manager replica shows status **InSync** in the target region

### What to Verify Before Step 5 Approval

- [ ] ECS service in target region shows desired task count running (ECS console > Clusters > `airporthub-cluster` > Service)
- [ ] ALB health check passing — target group shows healthy targets
- [ ] Application responds — `https://<cloudfront-domain>/api/health` returns `{"status": "healthy"}`

### What Happens If You Decline

Declining an approval gate **stops the execution immediately**. The system does NOT roll back — whatever steps completed before the gate remain in effect.

- **Decline at Step 3**: DocumentDB has already switched over but compute is still in the old region. Start a new execution targeting the original region to reverse Step 1.
- **Decline at Step 5**: ECS is scaled up in the target region, but cleanup (Step 6) won't run. Manually scale down the source ECS or start a new failback execution.

### Timeout Behavior

If an approval gate is not approved or declined within its timeout window, the execution **fails**. You can investigate and start a new execution from the plan page.

---

## How CloudFront Failover Works

CloudFront failover operates at the **data plane** via an origin group — there is no ARC step or Lambda that switches the CloudFront origin during failover.

### Origin Group Configuration

| Component | Value |
|---|---|
| Primary origin | `alb-primary` — VPC Origin to internal ALB in us-east-1 |
| Secondary origin | `alb-secondary` — VPC Origin to internal ALB in us-east-2 |
| Origin group | `alb-origin-group` — failover on HTTP 500, 502, 503, 504 |
| Default behavior | GET/HEAD/OPTIONS → origin group |

When CloudFront receives a GET/HEAD/OPTIONS request, it routes to the primary origin. If the primary returns 500/502/503/504, CloudFront **automatically retries** the same request against the secondary origin — no control-plane API call needed, no DNS TTL delay.

### Write Operations (POST/PUT/DELETE)

> [!IMPORTANT]
> **Origin group failover only covers GET/HEAD/OPTIONS.** Write operations route directly to the primary origin and are unavailable until ARC scales ECS in the recovery region.

Write paths are configured as 6 separate cache behaviors that all point directly to `alb-primary`:

- `/api/flights`, `/api/flights/*`
- `/api/airports`, `/api/airports/*`
- `/api/crew`, `/api/crew/*`

This is a documented tradeoff — the dashboard is read-heavy, so the origin group covers the critical read path. Writes resume once Step 4 (ECS scale-up) completes and CloudFront's origin group routes to the newly active secondary.

### Why No Control-Plane Switch in the ARC Plan

VPC Origins route traffic over AWS's internal backbone. Both ALBs are **internal-only** (no public IP) and only reachable through CloudFront's managed network interfaces. Because the origin group handles failover automatically at request time:

- There is **no DNS TTL delay** — failover is instant per-request
- There is **no Lambda** that calls `UpdateDistribution`
- The ARC plan does not include a CloudFront step

This aligns with the [Well-Architected Reliability Pillar guidance](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_withstand_component_failures_avoid_control_plane.html) to use data-plane mechanisms over control-plane dependencies during failures.

### Two-Phase Deployment

The origin group requires VPC Origins in both regions. Since the secondary VPC Origin doesn't exist until the secondary stack deploys, `deploy.py` uses a two-phase approach:

1. **Deploy primary** — CloudFront with single origin, no origin group
2. **Deploy secondary** — creates its VPC Origin, outputs `VpcOriginId`
3. **Re-deploy primary** with `SecondaryVpcOriginId` parameter — activates the origin group

> [!NOTE]
> This two-phase deployment is handled automatically by `deploy.py`. You only need to be aware of it if deploying manually or troubleshooting the CloudFormation stacks.

---

## Execution Reports

Every plan execution generates a report with step-by-step timing, success/failure status, and error details. Use these for post-incident review and RTO measurement.

### Viewing in the Console

1. Open **Application Recovery Controller** > **Region switch**
2. Select the `airporthub-region-switch` plan
3. Choose the **Plan execution history** tab
4. Click an **Execution ID** to view step-by-step progress and results

### S3 Reports

Reports are automatically delivered to:

```
s3://airporthub-arc-reports-<ACCOUNT_ID>/
```

Use these for programmatic access, compliance evidence, or long-term retention.

---

## References

- [Execute a Region Switch Plan](https://docs.aws.amazon.com/r53recovery/latest/dg/plan-execution-rs.html)
- [AWS::ARCRegionSwitch::Plan CloudFormation Reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/AWS_ARCRegionSwitch.html)
- [ARC Region Switch Plan Trust Policy](https://docs.aws.amazon.com/r53recovery/latest/dg/security_iam_region_switch_trust_policy.html)
- [DocumentDB Global Cluster DR](https://docs.aws.amazon.com/documentdb/latest/developerguide/global-clusters-disaster-recovery.html)
- [ARC Region Switch Pricing](https://aws.amazon.com/application-recovery-controller/pricing/)
- [Well-Architected Reliability Pillar — Avoid Control Plane Dependencies](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_withstand_component_failures_avoid_control_plane.html)

# Failover Operations Guide — ARC Region Switch

This document is the **operator runbook** for executing and managing ARC Region Switch failovers. For architecture details and design decisions, see the [main README](../README.md#arc-region-switch-walkthrough).

---

## Quick Reference

| | |
|---|---|
| **DR Pattern** | Pilot Light (Active/Passive) |
| **Primary Region** | us-east-1 (N. Virginia) |
| **Recovery Region** | us-east-2 (Ohio) |
| **RTO Target** | 15 minutes |
| **RPO Target** | Near-zero (DocumentDB Global Cluster continuous replication) |
| **Trigger** | Manual — operator-initiated from ARC console |
| **Plan Name** | `airporthub-region-switch` |
| **Execution Reports** | S3 bucket: `airporthub-arc-reports-<ACCOUNT_ID>` |

---

## How to Start a Failover

### From the AWS Console

1. In the AWS Console, **navigate to the Region you want to activate** (us-east-2 for failover, us-east-1 for failback)
2. Open **Application Recovery Controller** > **Region switch**
3. Select the `airporthub-region-switch` plan
4. Choose **Execute plan**
5. If prompted, approve manual steps as they come up (see [Approving Manual Gates](#approving-manual-gates) below)

### From the CLI

```bash
aws arc-region-switch start-plan-execution \
  --plan-arn <PLAN_ARN> \
  --target-region us-east-2
```

> **Note**: The plan ARN is output by the `airporthub-arc-plan` CloudFormation stack. Retrieve it with:
> ```bash
> aws cloudformation describe-stacks \
>   --stack-name airporthub-arc-plan \
>   --query 'Stacks[0].Outputs[?OutputKey==`PlanArn`].OutputValue' \
>   --output text
> ```

---

## Plan Steps & Timeouts

Both failover and failback follow a 6-step structure. Step names differ slightly per direction.

| Step | Action | Timeout | Retry Interval |
|---|---|---|---|
| 1 | DocumentDB Global Cluster Switchover | 10 min | — |
| 2 | Seed Live Flight Data (FlightAware Lambda) | 5 min | 5 min |
| 3 | **Manual Approval** | 10 min | — |
| 4 | ECS Scale Up | 10 min | — |
| 5 | **Manual Approval** | 10 min | — |
| 6 | Parallel: FlightAware Child Plan + Scale Down Source ECS | 60 min | 10 min (scale-down) |

### Step Names by Direction

| Step | Failover (activate us-east-2) | Failback (activate us-east-1) |
|---|---|---|
| 3 | `FailoverApproval` | `FailbackApproval` |
| 5 | `FinalApproval` | `FinalApprovalFailback` |
---

## Approving Manual Gates

Steps 3 and 5 pause execution and wait for an authorized operator to approve. Approval is done through the AWS Console.

### Console Walkthrough

1. In **Application Recovery Controller** > **Region switch**, select the `airporthub-region-switch` plan
2. Click the active **Execution ID** in the Executions section
3. The step with a **Pending approval** badge is waiting for you
4. Click the pending step, review preceding results, then choose **Approve** or **Decline**
5. Execution resumes automatically within seconds of approval

### What to Verify Before Step 3 Approval

- [ ] DocumentDB switchover completed — check DocumentDB console in target region shows cluster role as **Writer**
- [ ] Flight data seed Lambda (Step 2) shows **Succeeded** in the execution timeline
- [ ] Secrets Manager replica shows status **InSync** in the target region

### What to Verify Before Step 5 Approval

- [ ] ECS service in target region shows desired task count running (ECS console > Clusters > `airporthub-cluster` > Service)
- [ ] CloudFront origin group is routing traffic — `https://<cloudfront-domain>/api/health` returns `{"status": "healthy"}`

### What Happens If You Decline

Declining an approval gate **stops the execution immediately**. The system does NOT roll back — whatever steps completed before the gate remain in effect. For example:

- If you decline at Step 3: DocumentDB has already switched over but compute is still in the old region. You would need to start a new execution targeting the original region to reverse Step 1.
- If you decline at Step 5: ECS is scaled up in the target region, but cleanup (Step 6) won't run. You'd need to manually scale down the source ECS or start a new failback execution.

### Timeout Behavior

If an approval gate is not approved or declined within **10 minutes**, the execution fails. You can investigate and start a new execution from the plan page.

### Who Can Approve

The operator must be signed in with the IAM role specified as `ApprovalRoleArn` during deployment. For SSO roles, the full IAM path is required:

```bash
# Get your role's full ARN (including IAM path)
aws sts get-caller-identity
# → arn:aws:sts::ACCOUNT:assumed-role/ROLE_NAME/session

aws iam get-role --role-name ROLE_NAME --query 'Role.Arn'
# → arn:aws:iam::ACCOUNT:role/aws-reserved/sso.amazonaws.com/ROLE_NAME
```

Using a short ARN (without the `/aws-reserved/sso.amazonaws.com/` path) causes `AccessDeniedException`.

---

## How CloudFront Failover Works

CloudFront failover is handled at the **data plane** via an origin group — there is no ARC step or Lambda that switches the CloudFront origin during failover.

### Origin Group Configuration

The CloudFront distribution is configured with:

- **Primary origin** (`alb-primary`): VPC Origin pointing to the internal ALB in us-east-1
- **Secondary origin** (`alb-secondary`): VPC Origin pointing to the internal ALB in us-east-2
- **Origin group** (`alb-origin-group`): Wraps both origins with automatic failover on HTTP 500, 502, 503, or 504

When CloudFront receives a request that matches the default cache behavior (GET/HEAD/OPTIONS), it routes to the primary origin. If the primary returns 500/502/503/504, CloudFront **automatically retries** the same request against the secondary origin — no control-plane API call needed.

### Write Operations (POST/PUT/DELETE)

Origin groups only support GET/HEAD/OPTIONS methods. Write operations are routed via separate cache behaviors that point directly to the primary origin (`alb-primary`). During a DR event, writes are unavailable until ARC scales up ECS in the recovery region. This is a documented tradeoff — the dashboard is read-heavy, so origin group failover covers the critical read path.

### Why No Control-Plane Switch?

VPC Origins route traffic over AWS's internal backbone. Both ALBs are internal (no public IP) and only reachable through CloudFront's managed network interfaces. Because the origin group handles failover automatically at request time:

- There is **no DNS TTL delay** — failover is instant per-request
- There is **no Lambda** that calls `UpdateDistribution`
- The ARC plan does not include a CloudFront step

### Two-Phase Deployment

The origin group requires VPC Origins in both regions. Since the secondary VPC Origin doesn't exist until the secondary stack deploys, `deploy.py` uses a two-phase approach:

1. Deploy primary (CloudFront with single origin, no origin group)
2. Deploy secondary (creates its VPC Origin, outputs `VpcOriginId`)
3. Re-deploy primary with `SecondaryVpcOriginId` parameter (activates origin group)

[![CloudFront Origin Group Failover](generated-diagrams/cloudfront-origin-group-failover.png)](generated-diagrams/cloudfront-origin-group-failover.png)

---

## Execution Reports

Every plan execution generates a report with step-by-step timing, success/failure status, and error details. Use these for post-incident review and RTO measurement.

**To view execution history in the console:**

1. Open **Application Recovery Controller** > **Region switch** in the [AWS Console](https://console.aws.amazon.com)
2. Select the `airporthub-region-switch` plan
3. Choose the **Plan execution history** tab to see all past executions
4. Click an **Execution ID** to view step-by-step progress and results

Reports are also automatically delivered to S3 at `s3://airporthub-arc-reports-<ACCOUNT_ID>/` for programmatic access, compliance evidence, or long-term retention.

---

## Call for action

- [Execute a Region Switch Plan](https://docs.aws.amazon.com/r53recovery/latest/dg/plan-execution-rs.html)
- [AWS::ARCRegionSwitch::Plan CloudFormation Reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/AWS_ARCRegionSwitch.html)
- [ARC Region Switch Plan Trust Policy](https://docs.aws.amazon.com/r53recovery/latest/dg/security_iam_region_switch_trust_policy.html)
- [DocumentDB Global Cluster DR](https://docs.aws.amazon.com/documentdb/latest/developerguide/global-clusters-disaster-recovery.html)
- [ARC Region Switch Pricing](https://aws.amazon.com/application-recovery-controller/pricing/)

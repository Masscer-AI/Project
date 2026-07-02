# Masscer AWS Infrastructure (Pulumi + TypeScript)

This directory uses **Pulumi with Node.js + TypeScript** and deploys the application on **ECS with EC2 capacity**.

## Project structure

- `index.ts`: orchestration/composition layer only.
- `modules/config.ts`: stack config + secrets.
- `modules/networking.ts`: VPC, subnets, route tables, IGW.
- `modules/security-groups.ts`: ALB/ECS/DB/Redis/EFS SGs.
- `modules/artifacts.ts`: S3 buckets, ECR repos, log group.
- `modules/ecs-base.ts`: ECS cluster, capacity provider, EC2 ASG, IAM roles.
- `modules/data-services.ts`: RDS, Redis, EFS + mount targets.
- `modules/routing.ts`: ALB listeners/rules/target groups.
- `modules/service-discovery.ts`: Cloud Map namespace/service for Chroma.
- `modules/ecs-services.ts`: task definitions + ECS services (Django/FastAPI/Celery/Chroma).

## Prerequisites

- [Pulumi CLI](https://www.pulumi.com/docs/iac/download-install/)
- [direnv](https://direnv.net/)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- Node.js 20+

## Quick start on a new machine

Use this checklist when setting up deploy on any computer (laptop, CI runner, etc.).

### 1. Clone and install

```bash
git clone <repo-url> masscer
cd masscer/pulumi
npm install
```

### 2. AWS credentials

Add the `masscer-prod` profile to `~/.aws/config` and `~/.aws/credentials` (or SSO). At minimum in `~/.aws/config`:

```ini
[profile masscer-prod]
region = us-east-1
```

The IAM user needs deploy permissions **and** read/write access to the Pulumi state bucket `masscer-pulumi-state`.

Verify:

```bash
aws sts get-caller-identity --profile masscer-prod
```

On Git Bash / Windows, pass `--profile masscer-prod` explicitly if direnv is not loaded yet.

### 3. Pulumi passphrase

Create `pulumi/.passphrase` with the team passphrase (shared out-of-band — never commit it):

```bash
echo "<passphrase>" > .passphrase
```

### 4. direnv

```bash
cp .envrc.template .envrc
direnv allow
```

This sets `AWS_PROFILE=masscer-prod`, `PULUMI_STACK=prod`, and loads the passphrase file.

### 5. Pulumi backend (S3) and stack

State is stored in S3, not on disk. Run once per machine:

```bash
pulumi login 's3://masscer-pulumi-state?region=us-east-1'
pulumi stack select prod
```

Verify:

```bash
pulumi about | grep -A2 Backend
# URL should be s3://masscer-pulumi-state?region=us-east-1

pulumi preview
# Should show mostly "unchanged" resources, not a full recreate
```

### 6. Deploy

```bash
./deploy.sh
```

## Pulumi state and secrets

| What | Where | In git? |
|------|-------|---------|
| IaC code | `pulumi/*.ts` | Yes |
| Stack config | `Pulumi.prod.yaml` | Yes (secrets encrypted) |
| Decryption key | `.passphrase` | No |
| Resource state | `s3://masscer-pulumi-state` | No (in AWS) |

- `Pulumi.prod.yaml` is committed. Secrets use `pulumi config set --secret` and appear as `secure: v1:...` in the file.
- `.envrc` and `.passphrase` are gitignored.
- You do **not** copy `~/.pulumi/stacks/` between machines — state lives in S3.

### Migrating state to S3 (already done for prod)

If you ever need to move from a local backend again:

```bash
pulumi login --local
pulumi stack select prod
pulumi stack export --file prod-state-backup.json

pulumi login 's3://masscer-pulumi-state?region=us-east-1'
pulumi stack init prod    # skip if stack already exists on S3
pulumi stack import --file prod-state-backup.json
pulumi preview
```

Keep `prod-state-backup.json` offline as a backup; it is gitignored.

## What this stack creates

- `ECR` repositories for Django and streaming images.
- `ECS` cluster with **EC2 Capacity Provider**.
- `Auto Scaling Group` + `Launch Template` for ECS instances.
- `ALB` with path-based routing:
  - `/v1/*`, `/admin/*`, `/static/*`, `/media/*` -> Django service
  - `/socket.io/*`, `/` -> FastAPI service
- ECS services:
  - `django` (medium task size: 1024 CPU / 2048 MiB)
  - `fastapi`
  - `celery-worker`
  - `celery-beat`
  - `chroma` (with EFS volume mounted at `/data`)
- `RDS PostgreSQL` instance.
- `ElastiCache Redis` replication group.
- CloudWatch log group.
- Two private/versioned/encrypted `S3` buckets for static/media.

## ECS on EC2 notes

- Cluster is configured to use EC2 capacity provider by default.
- EC2 instances use ECS-optimized AMI from AWS SSM public parameter.
- Networking is fully provisioned by Pulumi (custom VPC, public/private subnets, route tables, IGW).
- Chroma is reachable internally through Cloud Map DNS (`chroma.<prefix>.internal`).

## Greenfield stack (first-time only)

If you are creating infrastructure from scratch (not joining existing prod):

```bash
cd pulumi
npm install
pulumi login 's3://masscer-pulumi-state?region=us-east-1'
pulumi stack init prod
pulumi config set aws:region us-east-1
pulumi config set masscer-infra:environment prod
pulumi config set masscer-infra:namePrefix masscer-prod
pulumi config set masscer-infra:instanceType t3.medium
pulumi config set masscer-infra:asgMinSize 1
pulumi config set masscer-infra:asgDesiredSize 1
pulumi config set masscer-infra:asgMaxSize 2
pulumi config set masscer-infra:dbName masscer
pulumi config set masscer-infra:dbUsername masscer
pulumi config set --secret masscer-infra:dbPassword "<db-password>"
pulumi config set --secret masscer-infra:djangoSecretKey "<django-secret-key>"
pulumi config set masscer-infra:djangoImageTag latest
pulumi config set masscer-infra:streamingImageTag latest
```

Then deploy:

```bash
pulumi preview
pulumi up
```

## Django post-deploy tasks

`deploy.sh` runs these one-off ECS tasks after each deploy (same task definition as the django service):
- `python manage.py migrate`
- `python manage.py sync_subscription_plans`
- `python manage.py sync_organization_subscriptions`

Network/subnets/SGs/capacity provider are read from the django ECS service (same idea as darwin-app’s `release_command.sh`).

Manual run (after `pulumi up` so `djangoTaskDefinitionArn` matches the image you want):

```bash
export CLUSTER="$(pulumi stack output ecsClusterName)"
export DJANGO_SERVICE_NAME="$(pulumi stack output djangoServiceName)"
export DJANGO_TASK_DEFINITION_ARN="$(pulumi stack output djangoTaskDefinitionArn)"
MANAGE_COMMAND_NAME=migrate bash ecs-run-migrate.sh
MANAGE_COMMAND_NAME=sync_subscription_plans bash ecs-run-migrate.sh
MANAGE_COMMAND_NAME=sync_organization_subscriptions bash ecs-run-migrate.sh
```

This uses the **same CPU/memory as the django task** (e.g. 1024 / 2048). If placement fails, scale the ASG or temporarily reduce other services—same as any extra awsvpc task.

## One-command deploy (local)

From this `pulumi/` directory (with direnv loaded), you can run:

```bash
./deploy.sh
```

Optional flags:

```bash
./deploy.sh --stack prod --region us-east-1
./deploy.sh --skip-bootstrap
./deploy.sh --skip-migrations  # skips migrate + sync commands
./deploy.sh --require-migrations
./deploy.sh --post-deploy-only
```

Notes:
- By default, deploy continues even if one-off Django tasks cannot be placed (common with EC2 CPU/ENI limits).  
  Use `--require-migrations` when you want deploy to fail hard on migrate/sync errors.
- One-off ECS tasks print progress every ~30s while waiting. You can tune timeout with:
  `ECS_ONEOFF_TIMEOUT_SECONDS=900` (default 900 seconds).
- ENI attach startup failures are retried automatically (default up to 3 attempts):
  - `ECS_ONEOFF_MAX_RETRIES=3`
  - `ECS_ONEOFF_RETRY_DELAY_SECONDS=20`
- By default, each deploy generates a unique image tag (`deploy-<UTC timestamp>-<git sha>`) to force a fresh ECS rollout.

## Custom domains (Route53)

To use custom domains with ALB + HTTPS, set these stack config keys:

```yaml
masscer-infra:rootDomain: masscer.ai
masscer-infra:appDomain: app.masscer.ai
masscer-infra:coreDomain: core.masscer.ai
```

What Pulumi configures automatically when those keys are set:
- ACM wildcard certificate for `*.masscer.ai` (DNS validation in Route53)
- HTTPS listener on ALB (443) + HTTP->HTTPS redirect
- Route53 alias records for `app.masscer.ai` and `core.masscer.ai`
- Host-based routing:
  - `core.masscer.ai` -> Django (all paths)
  - `app.masscer.ai` -> FastAPI by default, Django for `/v1/*`, `/static/*`, `/media/*`

Manual prerequisite:
- The public hosted zone for `masscer.ai` must already exist in Route53 in this AWS account.

## Why no Nginx service

You are correct: for this architecture, a separate Nginx container is optional.
ALB handles:
- Path-based routing between Django and FastAPI.
- WebSocket upgrade support for `/socket.io/*`.

Nginx is still useful only if you need custom reverse-proxy features not provided by ALB.

## Important production hardening

- Move from default VPC to dedicated VPC/private subnets/NAT.
- Add HTTPS listener + ACM certificate on ALB.
- Store runtime secrets in AWS Secrets Manager/SSM and inject into task definitions.
- Use Multi-AZ setup for RDS/Redis and EFS mount targets in multiple subnets.
- Add CI/CD for image build and ECS deployment.

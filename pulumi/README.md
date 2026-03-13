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

## Darwin-style workflow with direnv

This project supports the same style workflow you described:

1) Install dependencies:

```bash
cd pulumi
npm install
```

2) Configure AWS profile in `~/.aws/config`:

```ini
[profile masscer-prod]
region = us-east-1
```

3) Configure direnv (simple):

```bash
cp .envrc.template .envrc
echo "<your-passphrase>" > .passphrase
direnv allow
```

4) Select stack (if needed):

```bash
pulumi stack select prod || pulumi stack init prod
```

5) Preview / deploy:

```bash
pulumi preview
pulumi up --refresh
```

Notes:
- `.envrc` and `.passphrase` are gitignored.
- `.envrc.template` is intentionally minimal:
  - loads `PULUMI_CONFIG_PASSPHRASE_FILE` from `.passphrase` (if present)
  - sets `AWS_PROFILE=masscer-prod`
  - sets `PULUMI_STACK=prod`

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

## Quick start

1) Install Pulumi CLI and authenticate (`pulumi login`).

2) Install dependencies:

```bash
cd pulumi
npm install
```

3) Initialize and configure stack:

```bash
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

4) Deploy:

```bash
pulumi preview
pulumi up
```

5) Run Django migrations as a one-off ECS task (after first deploy):

```bash
aws ecs run-task \
  --cluster <ecsClusterName-output> \
  --task-definition <djangoMigrateTaskDefinitionArn-output> \
  --launch-type EC2 \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}"
```

## One-command deploy (local)

From this `pulumi/` directory (with direnv loaded), you can run:

```bash
./deploy.sh
```

Optional flags:

```bash
./deploy.sh --stack prod --region us-east-1
./deploy.sh --skip-bootstrap
./deploy.sh --skip-migrations
./deploy.sh --require-migrations
```

Notes:
- By default, deploy continues even if the one-off migration task cannot be placed (common with EC2 ENI limits).  
  Use `--require-migrations` when you want deploy to fail hard on migration errors.
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

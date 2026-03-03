# Masscer AWS Infrastructure (Pulumi + TypeScript)

This directory uses **Pulumi with Node.js + TypeScript** and deploys the application on **ECS with EC2 capacity**.

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
- Default networking uses the **default VPC + default subnets** (good for bootstrap; can be migrated later to a custom VPC).
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
pulumi stack init dev
pulumi config set aws:region us-east-1
pulumi config set masscer-infra:environment dev
pulumi config set masscer-infra:namePrefix masscer-dev
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
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

## Automated deploy with GitHub Actions

Workflow file: `.github/workflows/deploy-aws-ecs-ec2.yml`

It automates:
- Build and push Django + Streaming images to ECR (tag = commit SHA).
- `pulumi up` using those image tags.
- Run one-off ECS migration task.
- If migration succeeds, force new deployment for Django/FastAPI/Celery/Chroma services.

Required GitHub secrets:
- `AWS_DEPLOY_ROLE_ARN`: IAM role for GitHub OIDC.
- `PULUMI_ACCESS_TOKEN`: Pulumi Cloud token (if using Pulumi Cloud backend).

Trigger:
- On `push` to `main` (paths scoped to app/infra changes).
- Manual run via `workflow_dispatch` (select stack and region).

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

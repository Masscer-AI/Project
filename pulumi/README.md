# Masscer AWS Infrastructure (Pulumi + TypeScript)

Pulumi (Node.js + TypeScript) deploying the app on **ECS with EC2 capacity**.
State lives in S3 (`s3://masscer-pulumi-state`), secrets are encrypted with a passphrase.

## Prerequisites

- [Pulumi CLI](https://www.pulumi.com/docs/iac/download-install/)
- [direnv](https://direnv.net/)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- Node.js 20+

## Setup on a new machine

### 1. Clone and install

```bash
git clone <repo-url> masscer
cd masscer/pulumi
npm install
```

### 2. AWS credentials

Add the `masscer-prod` profile to `~/.aws/config` and `~/.aws/credentials` (or SSO).
The profile needs real credentials (access keys, or `role_arn` + `source_profile`) — a region alone is not enough.

```ini
# ~/.aws/config
[profile masscer-prod]
region = us-east-1
```

The IAM identity needs deploy permissions **and** read/write access to the state bucket `masscer-pulumi-state`.

Verify:

```bash
aws sts get-caller-identity --profile masscer-prod
```

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
pulumi about | grep -A2 Backend   # URL should be s3://masscer-pulumi-state?region=us-east-1
pulumi preview                    # mostly "unchanged", not a full recreate
```

### 6. Provider secrets

Set provider credentials as Pulumi secrets rather than committing them to a stack file:

```bash
pulumi config set-secret elevenLabsApiKey '<ELEVENLABS_API_KEY>'
```

## Deploy

From the `pulumi/` directory (with direnv loaded):

```bash
./deploy.sh
```

Optional flags:

```bash
./deploy.sh --stack prod --region us-east-1
./deploy.sh --skip-bootstrap
./deploy.sh --skip-migrations      # skips migrate + sync commands
./deploy.sh --require-migrations   # fail hard on migrate/sync errors
./deploy.sh --post-deploy-only
```

Notes:
- Images are built for `linux/amd64` by default (ECS uses x86 instances). Override with `DOCKER_PLATFORM=linux/arm64` only if your cluster is ARM.
- By default deploy continues even if one-off Django tasks cannot be placed (common with EC2 CPU/ENI limits). Use `--require-migrations` to fail hard.
- One-off ECS tasks print progress every ~30s. Tune timeout with `ECS_ONEOFF_TIMEOUT_SECONDS=900` (default 900s).
- ENI attach failures are retried automatically: `ECS_ONEOFF_MAX_RETRIES=3`, `ECS_ONEOFF_RETRY_DELAY_SECONDS=20`.
- Each deploy generates a unique image tag (`deploy-<UTC timestamp>-<git sha>`) to force a fresh ECS rollout.

### Post-deploy tasks

`deploy.sh` runs these one-off ECS tasks after each deploy (same task definition as the django service):
- `python manage.py migrate`
- `python manage.py sync_subscription_plans`
- `python manage.py sync_organization_subscriptions`

Manual run (after `pulumi up` so `djangoTaskDefinitionArn` matches the image you want):

```bash
export CLUSTER="$(pulumi stack output ecsClusterName)"
export DJANGO_SERVICE_NAME="$(pulumi stack output djangoServiceName)"
export DJANGO_TASK_DEFINITION_ARN="$(pulumi stack output djangoTaskDefinitionArn)"
MANAGE_COMMAND_NAME=migrate bash ecs-run-migrate.sh
MANAGE_COMMAND_NAME=sync_subscription_plans bash ecs-run-migrate.sh
MANAGE_COMMAND_NAME=sync_organization_subscriptions bash ecs-run-migrate.sh
```

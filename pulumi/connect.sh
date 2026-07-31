#!/usr/bin/env bash
# Open an interactive shell in a running Django ECS task via ECS Exec.
set -euo pipefail

PULUMI_DIR="$(cd "$(dirname "$0")" && pwd)"
STACK="${PULUMI_STACK:-prod}"
AWS_REGION="${AWS_REGION:-us-east-1}"
CONTAINER="${CONTAINER:-django}"

# Fallback when direnv was not loaded in current shell.
if [[ -z "${PULUMI_CONFIG_PASSPHRASE:-}" && -z "${PULUMI_CONFIG_PASSPHRASE_FILE:-}" && -f "$PULUMI_DIR/.passphrase" ]]; then
  export PULUMI_CONFIG_PASSPHRASE_FILE="$PULUMI_DIR/.passphrase"
fi

cd "$PULUMI_DIR"

# Pulumi's current backend is global per machine; pin Masscer state so another
# project's `pulumi login` cannot steal this connect.
PULUMI_BACKEND_URL="${PULUMI_BACKEND_URL:-s3://masscer-pulumi-state?region=${AWS_REGION}}"
echo "==> Pulumi login ($PULUMI_BACKEND_URL)"
pulumi login "$PULUMI_BACKEND_URL"

pulumi stack select "$STACK" >/dev/null

CLUSTER="$(pulumi stack output ecsClusterName)"
SERVICE="$(pulumi stack output djangoServiceName)"

TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER" \
  --service-name "$SERVICE" \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text)

if [[ -z "$TASK_ARN" || "$TASK_ARN" == "None" ]]; then
  echo "Error: no RUNNING tasks for $SERVICE in $CLUSTER" >&2
  exit 1
fi

echo "Connecting to $TASK_ARN ($CONTAINER)..."
exec aws ecs execute-command \
  --cluster "$CLUSTER" \
  --task "$TASK_ARN" \
  --container "$CONTAINER" \
  --interactive \
  --command "/bin/sh"

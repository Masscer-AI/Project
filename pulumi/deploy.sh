#!/bin/bash

set -euo pipefail

PULUMI_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$PULUMI_DIR/.." && pwd)"

STACK="${PULUMI_STACK:-prod}"
AWS_REGION="${AWS_REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-}"
SKIP_BOOTSTRAP=0
SKIP_MIGRATIONS=0
REQUIRE_MIGRATIONS=0

# Fallback when direnv was not loaded in current shell.
if [[ -z "${PULUMI_CONFIG_PASSPHRASE:-}" && -z "${PULUMI_CONFIG_PASSPHRASE_FILE:-}" && -f "$PULUMI_DIR/.passphrase" ]]; then
  export PULUMI_CONFIG_PASSPHRASE_FILE="$PULUMI_DIR/.passphrase"
fi

usage() {
  echo "Usage:"
  echo "  ./deploy.sh [options]"
  echo ""
  echo "Options:"
  echo "  --stack <name>         Pulumi stack name (default: prod)"
  echo "  --region <region>      AWS region (default: us-east-1)"
  echo "  --image-tag <tag>      Docker image tag (default: auto timestamp tag)"
  echo "  --skip-bootstrap       Skip initial pulumi up bootstrap step"
  echo "  --skip-migrations      Skip one-off Django migrations task"
  echo "  --require-migrations   Fail deploy when migration task cannot run or fails"
  echo "  -h, --help             Show this help"
  echo ""
  echo "Examples:"
  echo "  ./deploy.sh"
  echo "  ./deploy.sh --stack prod --region us-east-1 --image-tag v2026.03.10"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack)
      STACK="$2"
      shift 2
      ;;
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --image-tag)
      IMAGE_TAG="$2"
      shift 2
      ;;
    --skip-bootstrap)
      SKIP_BOOTSTRAP=1
      shift
      ;;
    --skip-migrations)
      SKIP_MIGRATIONS=1
      shift
      ;;
    --require-migrations)
      REQUIRE_MIGRATIONS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown flag: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$IMAGE_TAG" ]]; then
  IMAGE_TAG="deploy-$(date -u +%Y%m%d%H%M%S)"
  if GIT_SHA="$(git -C "$ROOT_DIR" rev-parse --short=8 HEAD 2>/dev/null)"; then
    IMAGE_TAG="${IMAGE_TAG}-${GIT_SHA}"
  fi
fi

for cmd in aws pulumi docker node; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: '$cmd' is required but not installed."
    exit 1
  fi
done

echo "==> Deploy configuration"
echo "Stack:      $STACK"
echo "AWS region: $AWS_REGION"
echo "Image tag:  $IMAGE_TAG"
echo ""

cd "$PULUMI_DIR"

if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi

pulumi stack select "$STACK" || pulumi stack init "$STACK"
pulumi config set aws:region "$AWS_REGION"

if [[ "$SKIP_BOOTSTRAP" -eq 0 ]]; then
  echo "==> Bootstrap infrastructure (ensure ECR repos exist)"
  pulumi up --yes --skip-preview
fi

echo "==> Resolve ECR repository URLs"
DJANGO_REPO="$(pulumi stack output djangoEcrRepositoryUrl)"
STREAMING_REPO="$(pulumi stack output streamingEcrRepositoryUrl)"

if [[ -z "$DJANGO_REPO" || -z "$STREAMING_REPO" ]]; then
  echo "Error: could not resolve ECR repository outputs."
  exit 1
fi

ECR_REGISTRY="${DJANGO_REPO%%/*}"
echo "==> Login to ECR registry: $ECR_REGISTRY"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "==> Build and push Django image"
docker build -t "${DJANGO_REPO}:${IMAGE_TAG}" "$ROOT_DIR/server"
docker push "${DJANGO_REPO}:${IMAGE_TAG}"

echo "==> Build and push Streaming image"
docker build -t "${STREAMING_REPO}:${IMAGE_TAG}" "$ROOT_DIR/streaming"
docker push "${STREAMING_REPO}:${IMAGE_TAG}"

echo "==> Update Pulumi image tags and deploy"
pulumi config set masscer-infra:djangoImageTag "$IMAGE_TAG"
pulumi config set masscer-infra:streamingImageTag "$IMAGE_TAG"
pulumi up --yes

if [[ "$SKIP_MIGRATIONS" -eq 0 ]]; then
  echo "==> Run Django migrations as one-off ECS task"
  CLUSTER="$(pulumi stack output ecsClusterName)"
  DJANGO_SERVICE_NAME="$(pulumi stack output djangoServiceName)"
  DJANGO_TASK_DEFINITION_ARN="$(pulumi stack output djangoTaskDefinitionArn)"
  export CLUSTER DJANGO_SERVICE_NAME DJANGO_TASK_DEFINITION_ARN

  if bash "$PULUMI_DIR/ecs-run-migrate.sh"; then
    :
  else
    echo "Warning: migration task failed or could not be scheduled."
    if [[ "$REQUIRE_MIGRATIONS" -eq 1 ]]; then
      echo "Error: --require-migrations set; aborting deploy."
      exit 1
    fi
    echo "Continuing deploy because --require-migrations was not set."
  fi
fi

echo "==> Force ECS service rollout"
CLUSTER="$(pulumi stack output ecsClusterName)"
DJANGO_SERVICE="$(pulumi stack output djangoServiceName)"
FASTAPI_SERVICE="$(pulumi stack output fastapiServiceName)"
CELERY_WORKER_SERVICE="$(pulumi stack output celeryWorkerServiceName)"
CELERY_BEAT_SERVICE="$(pulumi stack output celeryBeatServiceName)"

for SERVICE in "$DJANGO_SERVICE" "$FASTAPI_SERVICE" "$CELERY_WORKER_SERVICE" "$CELERY_BEAT_SERVICE"; do
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$SERVICE" \
    --force-new-deployment >/dev/null
done

echo ""
echo "Deploy completed successfully."
echo "ALB URL: $(pulumi stack output appBaseUrl)"

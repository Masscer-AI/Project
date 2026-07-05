#!/bin/bash

set -euo pipefail

PULUMI_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$PULUMI_DIR/.." && pwd)"

STACK="${PULUMI_STACK:-prod}"
AWS_REGION="${AWS_REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-}"
# ECS nodes are x86 (e.g. t3.*). Building on Apple Silicon without this yields arm64-only images.
DOCKER_PLATFORM="${DOCKER_PLATFORM:-linux/amd64}"
SKIP_BOOTSTRAP=0
SKIP_MIGRATIONS=0
REQUIRE_MIGRATIONS=0
POST_DEPLOY_ONLY=0

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
  echo "  --skip-migrations      Skip one-off Django post-deploy tasks (migrate + syncs)"
  echo "  --require-migrations   Fail deploy when any Django one-off task cannot run or fails"
  echo "  --post-deploy-only     Run only Django post-deploy tasks (no build/pulumi up/rollout)"
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
    --post-deploy-only)
      POST_DEPLOY_ONLY=1
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

if [[ "$POST_DEPLOY_ONLY" -eq 0 && -z "$IMAGE_TAG" ]]; then
  IMAGE_TAG="deploy-$(date -u +%Y%m%d%H%M%S)"
  if GIT_SHA="$(git -C "$ROOT_DIR" rev-parse --short=8 HEAD 2>/dev/null)"; then
    IMAGE_TAG="${IMAGE_TAG}-${GIT_SHA}"
  fi
fi

for cmd in aws pulumi node; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: '$cmd' is required but not installed."
    exit 1
  fi
done
if [[ "$POST_DEPLOY_ONLY" -eq 0 ]] && ! command -v docker >/dev/null 2>&1; then
  echo "Error: 'docker' is required but not installed."
  exit 1
fi

echo "==> Deploy configuration"
echo "Stack:      $STACK"
echo "AWS region: $AWS_REGION"
if [[ "$POST_DEPLOY_ONLY" -eq 0 ]]; then
  echo "Image tag:  $IMAGE_TAG"
else
  echo "Mode:       post-deploy-only"
fi
echo ""

cd "$PULUMI_DIR"

if [[ "$POST_DEPLOY_ONLY" -eq 0 ]]; then
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
fi

pulumi stack select "$STACK" || pulumi stack init "$STACK"
pulumi config set aws:region "$AWS_REGION"

run_django_manage_oneoff() {
  local command_name="$1"
  local label="$2"
  echo "==> ${label}"
  if MANAGE_COMMAND_NAME="$command_name" TASK_LABEL="$label" bash "$PULUMI_DIR/ecs-run-migrate.sh"; then
    return 0
  fi
  echo "Warning: ${label} task failed or could not be scheduled."
  if [[ "$REQUIRE_MIGRATIONS" -eq 1 ]]; then
    echo "Error: --require-migrations set; aborting deploy."
    exit 1
  fi
  echo "Continuing deploy because --require-migrations was not set."
  return 1
}

run_post_deploy_tasks() {
  if [[ "$SKIP_MIGRATIONS" -eq 1 ]]; then
    echo "==> Skipping Django post-deploy tasks (--skip-migrations)"
    return 0
  fi
  echo "==> Run Django one-off post-deploy tasks"
  CLUSTER="$(pulumi stack output ecsClusterName)"
  DJANGO_SERVICE_NAME="$(pulumi stack output djangoServiceName)"
  DJANGO_TASK_DEFINITION_ARN="$(pulumi stack output djangoTaskDefinitionArn)"
  export CLUSTER DJANGO_SERVICE_NAME DJANGO_TASK_DEFINITION_ARN

  if run_django_manage_oneoff "migrate" "Django migrate"; then
    run_django_manage_oneoff "sync_subscription_plans" "Django sync_subscription_plans"
    run_django_manage_oneoff "sync_organization_subscriptions" "Django sync_organization_subscriptions"
  fi
}

if [[ "$POST_DEPLOY_ONLY" -eq 1 ]]; then
  run_post_deploy_tasks
  echo ""
  echo "Post-deploy tasks completed."
  exit 0
fi

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

echo "==> Build and push Django image (platform: ${DOCKER_PLATFORM})"
docker build --platform "$DOCKER_PLATFORM" -t "${DJANGO_REPO}:${IMAGE_TAG}" "$ROOT_DIR/server"
docker push "${DJANGO_REPO}:${IMAGE_TAG}"

echo "==> Build and push Streaming image"
# Vite inlines VITE_GOOGLE_CLIENT_ID at build time. Resolve in order: env → root .env → SSM (after Pulumi creates it).
resolve_vite_google_client_id() {
  if [[ -n "${VITE_GOOGLE_CLIENT_ID:-}" ]]; then
    echo "Vite: using VITE_GOOGLE_CLIENT_ID from environment"
    return 0
  fi
  if [[ -n "${GOOGLE_CLIENT_ID:-}" ]]; then
    export VITE_GOOGLE_CLIENT_ID="$GOOGLE_CLIENT_ID"
    echo "Vite: using GOOGLE_CLIENT_ID from environment"
    return 0
  fi
  local env_file="$ROOT_DIR/.env"
  if [[ -f "$env_file" ]]; then
    local v
    v=$(grep -E "^[[:space:]]*VITE_GOOGLE_CLIENT_ID=" "$env_file" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//") || true
    if [[ -n "$v" ]]; then
      export VITE_GOOGLE_CLIENT_ID="$v"
      echo "Vite: using VITE_GOOGLE_CLIENT_ID from .env"
      return 0
    fi
    v=$(grep -E "^[[:space:]]*GOOGLE_CLIENT_ID=" "$env_file" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//") || true
    if [[ -n "$v" ]]; then
      export VITE_GOOGLE_CLIENT_ID="$v"
      echo "Vite: using GOOGLE_CLIENT_ID from .env"
      return 0
    fi
  fi
  local name_prefix
  name_prefix="$(pulumi config get masscer-infra:namePrefix 2>/dev/null || true)"
  if [[ -n "$name_prefix" ]]; then
    local ssm_path="/${name_prefix}/providers/GOOGLE_OAUTH_CLIENT_ID"
    local val
    if val=$(aws ssm get-parameter --name "$ssm_path" --query Parameter.Value --output text --region "$AWS_REGION" 2>/dev/null); then
      if [[ "$val" == "__UNSET__" ]]; then
        val=""
      fi
      if [[ -n "$val" ]]; then
        export VITE_GOOGLE_CLIENT_ID="$val"
        echo "Vite: using GOOGLE_OAUTH_CLIENT_ID from SSM ($ssm_path)"
        return 0
      fi
    fi
  fi
  echo "Warning: VITE_GOOGLE_CLIENT_ID not found (env, .env, or SSM). Google Sign-In will be omitted in the bundle."
  return 0
}

resolve_vite_google_client_id

docker build --platform "$DOCKER_PLATFORM" \
  --build-arg "VITE_GOOGLE_CLIENT_ID=${VITE_GOOGLE_CLIENT_ID:-}" \
  -t "${STREAMING_REPO}:${IMAGE_TAG}" "$ROOT_DIR/streaming"
docker push "${STREAMING_REPO}:${IMAGE_TAG}"

echo "==> Update Pulumi image tags and deploy"
pulumi config set masscer-infra:djangoImageTag "$IMAGE_TAG"
pulumi config set masscer-infra:streamingImageTag "$IMAGE_TAG"
pulumi up --yes

run_post_deploy_tasks

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

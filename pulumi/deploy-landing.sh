#!/bin/bash
# Build the marketing site and publish it to the apex domain (S3 + CloudFront).
# Requires the landing stack resources from `pulumi up` (landingBucketName, landingDistributionId).

set -euo pipefail

PULUMI_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$PULUMI_DIR/.." && pwd)"
LANDING_DIR="$ROOT_DIR/landing"

STACK="${PULUMI_STACK:-prod}"
AWS_REGION="${AWS_REGION:-us-east-1}"

if [[ -z "${PULUMI_CONFIG_PASSPHRASE:-}" && -z "${PULUMI_CONFIG_PASSPHRASE_FILE:-}" && -f "$PULUMI_DIR/.passphrase" ]]; then
  export PULUMI_CONFIG_PASSPHRASE_FILE="$PULUMI_DIR/.passphrase"
fi

usage() {
  echo "Usage:"
  echo "  ./deploy-landing.sh [options]"
  echo ""
  echo "Options:"
  echo "  --stack <name>     Pulumi stack name (default: prod)"
  echo "  --region <region>  AWS region (default: us-east-1)"
  echo "  -h, --help         Show this help"
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

for cmd in aws pulumi npm; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: '$cmd' is required but not installed."
    exit 1
  fi
done

echo "==> Deploy landing site"
echo "Stack:      $STACK"
echo "AWS region: $AWS_REGION"
echo ""

cd "$PULUMI_DIR"

PULUMI_BACKEND_URL="${PULUMI_BACKEND_URL:-s3://masscer-pulumi-state?region=${AWS_REGION}}"
echo "==> Pulumi login ($PULUMI_BACKEND_URL)"
pulumi login "$PULUMI_BACKEND_URL"
pulumi stack select "$STACK"

BUCKET="$(pulumi stack output landingBucketName 2>/dev/null || true)"
DISTRIBUTION_ID="$(pulumi stack output landingDistributionId 2>/dev/null || true)"
LANDING_URL="$(pulumi stack output landingUrl 2>/dev/null || true)"

if [[ -z "$BUCKET" || -z "$DISTRIBUTION_ID" ]]; then
  echo "Error: landingBucketName / landingDistributionId not found."
  echo "Run 'pulumi up' first so the landing CloudFront stack exists."
  exit 1
fi

echo "==> Build landing (Vite)"
cd "$LANDING_DIR"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
npm run build

echo "==> Sync dist/ → s3://${BUCKET}"
aws s3 sync "$LANDING_DIR/dist" "s3://${BUCKET}" \
  --region "$AWS_REGION" \
  --delete \
  --cache-control "public,max-age=31536000,immutable" \
  --exclude "index.html" \
  --exclude "*.html"

aws s3 cp "$LANDING_DIR/dist/index.html" "s3://${BUCKET}/index.html" \
  --region "$AWS_REGION" \
  --cache-control "public,max-age=0,must-revalidate" \
  --content-type "text/html"

# Other HTML entrypoints (if any) should also avoid long cache.
shopt -s nullglob
for html in "$LANDING_DIR/dist"/*.html; do
  base="$(basename "$html")"
  if [[ "$base" == "index.html" ]]; then
    continue
  fi
  aws s3 cp "$html" "s3://${BUCKET}/${base}" \
    --region "$AWS_REGION" \
    --cache-control "public,max-age=0,must-revalidate" \
    --content-type "text/html"
done
shopt -u nullglob

echo "==> Invalidate CloudFront (${DISTRIBUTION_ID})"
INVALIDATION_ID="$(aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths "/*" \
  --query 'Invalidation.Id' \
  --output text)"

echo ""
echo "Landing deploy completed."
echo "URL:            ${LANDING_URL:-https://masscer.ai}"
echo "Bucket:         $BUCKET"
echo "Distribution:   $DISTRIBUTION_ID"
echo "Invalidation:   $INVALIDATION_ID"

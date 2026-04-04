#!/usr/bin/env bash
# Run Django migrations via ECS: same task definition as the django service, command overridden
# (same pattern as darwin-app django/release_command.sh). Network + capacity provider come from the service.
set -euo pipefail

CLUSTER="${CLUSTER:?}"
DJANGO_SERVICE_NAME="${DJANGO_SERVICE_NAME:?}"
TASK_DEF="${DJANGO_TASK_DEFINITION_ARN:?}"

SERVICE_ARN=$(aws ecs describe-services --cluster "$CLUSTER" --services "$DJANGO_SERVICE_NAME" \
  --query 'services[0].serviceArn' --output text)

if [[ -z "$SERVICE_ARN" || "$SERVICE_ARN" == "None" ]]; then
  echo "Error: ECS service not found: $DJANGO_SERVICE_NAME in cluster $CLUSTER" >&2
  exit 1
fi

CAPACITY_PROVIDER_STRATEGY=$(aws ecs describe-services \
  --cluster "$CLUSTER" \
  --services "$DJANGO_SERVICE_NAME" \
  --query 'services[0].capacityProviderStrategy' \
  --output json)

SUBNET_IDS=$(aws ecs describe-services \
  --cluster "$CLUSTER" \
  --services "$DJANGO_SERVICE_NAME" \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.subnets[]' \
  --output text | tr '\t' ',' | tr '\n' ',' | sed 's/,$//')

SECURITY_GROUP_IDS=$(aws ecs describe-services \
  --cluster "$CLUSTER" \
  --services "$DJANGO_SERVICE_NAME" \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.securityGroups[]' \
  --output text | tr '\t' ',' | tr '\n' ',' | sed 's/,$//')

ASSIGN_PUBLIC=$(aws ecs describe-services \
  --cluster "$CLUSTER" \
  --services "$DJANGO_SERVICE_NAME" \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.assignPublicIp' \
  --output text)

if [[ -z "$ASSIGN_PUBLIC" || "$ASSIGN_PUBLIC" == "None" ]]; then
  ASSIGN_PUBLIC="DISABLED"
fi

NW_JSON="awsvpcConfiguration={subnets=[${SUBNET_IDS}],securityGroups=[${SECURITY_GROUP_IDS}],assignPublicIp=${ASSIGN_PUBLIC}}"
OVERRIDES='{"containerOverrides": [{"name": "django", "command": ["python", "manage.py", "migrate"]}]}'

if [[ "$CAPACITY_PROVIDER_STRATEGY" == "null" || "$CAPACITY_PROVIDER_STRATEGY" == "[]" ]]; then
  RUN_TASK_RESPONSE=$(aws ecs run-task \
    --cluster "$CLUSTER" \
    --task-definition "$TASK_DEF" \
    --launch-type EC2 \
    --network-configuration "$NW_JSON" \
    --overrides "$OVERRIDES" \
    --output json)
else
  RUN_TASK_RESPONSE=$(aws ecs run-task \
    --cluster "$CLUSTER" \
    --task-definition "$TASK_DEF" \
    --capacity-provider-strategy "$CAPACITY_PROVIDER_STRATEGY" \
    --network-configuration "$NW_JSON" \
    --overrides "$OVERRIDES" \
    --output json)
fi

TASK_ARN=$(printf '%s' "$RUN_TASK_RESPONSE" | node -e 'const fs=require("fs"); const data=JSON.parse(fs.readFileSync(0,"utf8")); process.stdout.write(data.tasks?.[0]?.taskArn ?? "");')

if [[ -z "$TASK_ARN" || "$TASK_ARN" == "None" ]]; then
  echo "Error: failed to start migration task." >&2
  printf '%s\n' "$RUN_TASK_RESPONSE" | node -e '
    const fs=require("fs");
    const data=JSON.parse(fs.readFileSync(0,"utf8"));
    const failures=data.failures ?? [];
    if (failures.length === 0) {
      console.error("No ECS failures were returned.");
      process.exit(0);
    }
    console.error("ECS failures:");
    for (const failure of failures) {
      console.error(`- arn: ${failure.arn ?? "<none>"}`);
      console.error(`  reason: ${failure.reason ?? "<none>"}`);
      console.error(`  detail: ${failure.detail ?? "<none>"}`);
    }
  ' >&2
  exit 1
fi

aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN"
EXIT_CODE=$(aws ecs describe-tasks \
  --cluster "$CLUSTER" \
  --tasks "$TASK_ARN" \
  --query "tasks[0].containers[0].exitCode" \
  --output text)

echo "Migration task exit code: $EXIT_CODE"
if [[ "$EXIT_CODE" != "0" ]]; then
  exit 1
fi

#!/usr/bin/env bash
# Run a Django manage.py one-off command via ECS using the same task definition as
# the django service. Network + capacity provider come from the service.
set -euo pipefail

CLUSTER="${CLUSTER:?}"
DJANGO_SERVICE_NAME="${DJANGO_SERVICE_NAME:?}"
TASK_DEF="${DJANGO_TASK_DEFINITION_ARN:?}"
MANAGE_COMMAND_NAME="${MANAGE_COMMAND_NAME:-migrate}"
TASK_LABEL="${TASK_LABEL:-Django manage.py ${MANAGE_COMMAND_NAME}}"

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
OVERRIDES="{\"containerOverrides\": [{\"name\": \"django\", \"command\": [\"python\", \"manage.py\", \"${MANAGE_COMMAND_NAME}\"]}]}"
TIMEOUT_SECONDS="${ECS_ONEOFF_TIMEOUT_SECONDS:-900}"
POLL_SECONDS=5
MAX_RETRIES="${ECS_ONEOFF_MAX_RETRIES:-3}"
RETRY_DELAY_SECONDS="${ECS_ONEOFF_RETRY_DELAY_SECONDS:-20}"
ATTEMPT=1

while true; do
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
    echo "Error: failed to start task (${TASK_LABEL})." >&2
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

  echo "${TASK_LABEL} task started: $TASK_ARN (attempt ${ATTEMPT}/${MAX_RETRIES})"
  ELAPSED=0
  while true; do
    LAST_STATUS=$(aws ecs describe-tasks \
      --cluster "$CLUSTER" \
      --tasks "$TASK_ARN" \
      --query "tasks[0].lastStatus" \
      --output text)
    if [[ "$LAST_STATUS" == "STOPPED" ]]; then
      break
    fi
    if [ $((ELAPSED % 30)) -eq 0 ]; then
      CONTAINER_REASON=$(aws ecs describe-tasks \
        --cluster "$CLUSTER" \
        --tasks "$TASK_ARN" \
        --query "tasks[0].containers[0].reason" \
        --output text)
      if [[ -z "$CONTAINER_REASON" || "$CONTAINER_REASON" == "None" ]]; then
        echo "${TASK_LABEL} task status: ${LAST_STATUS} (waiting...)"
      else
        echo "${TASK_LABEL} task status: ${LAST_STATUS} (${CONTAINER_REASON})"
      fi
    fi
    if [ "$ELAPSED" -ge "$TIMEOUT_SECONDS" ]; then
      echo "Error: ${TASK_LABEL} task timed out after ${TIMEOUT_SECONDS}s." >&2
      aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK_ARN" --output json >&2
      exit 1
    fi
    sleep "$POLL_SECONDS"
    ELAPSED=$((ELAPSED + POLL_SECONDS))
  done

  EXIT_CODE=$(aws ecs describe-tasks \
    --cluster "$CLUSTER" \
    --tasks "$TASK_ARN" \
    --query "tasks[0].containers[?name=='django']|[0].exitCode" \
    --output text)
  STOP_CODE=$(aws ecs describe-tasks \
    --cluster "$CLUSTER" \
    --tasks "$TASK_ARN" \
    --query "tasks[0].stopCode" \
    --output text)
  STOPPED_REASON=$(aws ecs describe-tasks \
    --cluster "$CLUSTER" \
    --tasks "$TASK_ARN" \
    --query "tasks[0].stoppedReason" \
    --output text)
  CONTAINER_REASON=$(aws ecs describe-tasks \
    --cluster "$CLUSTER" \
    --tasks "$TASK_ARN" \
    --query "tasks[0].containers[?name=='django']|[0].reason" \
    --output text)
  CONTAINER_LAST_STATUS=$(aws ecs describe-tasks \
    --cluster "$CLUSTER" \
    --tasks "$TASK_ARN" \
    --query "tasks[0].containers[?name=='django']|[0].lastStatus" \
    --output text)

  echo "${TASK_LABEL} task exit code: $EXIT_CODE"
  if [[ "$EXIT_CODE" == "0" ]]; then
    break
  fi

  echo "${TASK_LABEL} task failure details:" >&2
  echo "  stopCode: ${STOP_CODE}" >&2
  echo "  stoppedReason: ${STOPPED_REASON}" >&2
  echo "  django container lastStatus: ${CONTAINER_LAST_STATUS}" >&2
  if [[ -n "$CONTAINER_REASON" && "$CONTAINER_REASON" != "None" ]]; then
    echo "  django container reason: ${CONTAINER_REASON}" >&2
  fi
  if [[ "$EXIT_CODE" == "None" ]]; then
    echo "  hint: container never reached a normal process exit (often placement/image-pull/startup failure)." >&2
  fi

  if [[ "$STOP_CODE" == "TaskFailedToStart" && "$STOPPED_REASON" == *"Unable to attach network interface to unused device index."* && "$ATTEMPT" -lt "$MAX_RETRIES" ]]; then
    ATTEMPT=$((ATTEMPT + 1))
    echo "Retrying ${TASK_LABEL} in ${RETRY_DELAY_SECONDS}s due to ENI attach failure (${ATTEMPT}/${MAX_RETRIES})..." >&2
    sleep "$RETRY_DELAY_SECONDS"
    continue
  fi

  exit 1
done

import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { AppConfig, Tags } from "./config";

export function createAppServices(args: {
  config: AppConfig;
  tags: Tags;
  region: { name: pulumi.Output<string> };
  appLogs: aws.cloudwatch.LogGroup;
  cluster: aws.ecs.Cluster;
  capacityProvider: aws.ecs.CapacityProvider;
  clusterCapacityProviders: aws.ecs.ClusterCapacityProviders;
  taskExecutionRole: aws.iam.Role;
  taskRole: aws.iam.Role;
  djangoRepo: aws.ecr.Repository;
  streamingRepo: aws.ecr.Repository;
  postgres: aws.rds.Instance;
  redis: aws.elasticache.ReplicationGroup;
  alb: aws.lb.LoadBalancer;
  djangoTargetGroup: aws.lb.TargetGroup;
  fastapiTargetGroup: aws.lb.TargetGroup;
  httpListener: aws.lb.Listener;
  appTasksSecurityGroupId: any;
  publicSubnetIds: any[];
  chromaImage: string;
  chromaEfsId: any;
  chromaMountTargets: aws.efs.MountTarget[];
  chromaDiscoveryServiceArn: any;
  chromaInternalHost: pulumi.Output<string>;
}) {
  const { config } = args;

  const dbConnectionString = pulumi.interpolate`postgres://${config.dbUsername}:${config.dbPassword}@${args.postgres.address}:${args.postgres.port}/${config.dbName}`;
  const redisBaseUrl = pulumi.interpolate`redis://${args.redis.primaryEndpointAddress}:${args.redis.port}`;
  const celeryBrokerUrl = pulumi.interpolate`${redisBaseUrl}/0`;
  const redisCacheUrl = pulumi.interpolate`${redisBaseUrl}/1`;
  const redisNotificationsUrl = pulumi.interpolate`${redisBaseUrl}/2`;
  const frontendUrl = pulumi.interpolate`http://${args.alb.dnsName}`;
  const apiBaseUrl = pulumi.interpolate`http://${args.alb.dnsName}`;
  const djangoAllowedHosts = pulumi.interpolate`${args.alb.dnsName}${config.allowedExtraHosts ? `,${config.allowedExtraHosts}` : ""}`;

  const djangoEnv = [
    { name: "DB_CONNECTION_STRING", value: dbConnectionString },
    { name: "SECRET_KEY", value: config.djangoSecretKey },
    { name: "CELERY_BROKER_URL", value: celeryBrokerUrl },
    { name: "CELERY_RESULT_BACKEND", value: celeryBrokerUrl },
    { name: "REDIS_CACHE_URL", value: redisCacheUrl },
    { name: "REDIS_NOTIFICATIONS_URL", value: redisNotificationsUrl },
    { name: "MEDIA_ROOT", value: "/app/storage" },
    { name: "CHROMA_HOST", value: args.chromaInternalHost },
    { name: "CHROMA_PORT", value: "8000" },
    { name: "API_BASE_URL", value: apiBaseUrl },
    { name: "ALLOWED_EXTRA_HOSTS", value: djangoAllowedHosts },
    { name: "OPENAI_API_KEY", value: config.openAiApiKey },
    { name: "ANTHROPIC_API_KEY", value: config.anthropicApiKey },
    { name: "XAI_API_KEY", value: config.xaiApiKey },
    { name: "PEXELS_API_KEY", value: config.pexelsApiKey },
    { name: "BRAVE_API_KEY", value: config.braveApiKey },
    { name: "BFL_API_KEY", value: config.bflApiKey },
    { name: "RUNWAY_API_KEY", value: config.runwayApiKey },
    { name: "WHATSAPP_GRAPH_API_TOKEN", value: config.whatsappGraphApiToken },
    { name: "WHATSAPP_WEBHOOK_VERIFY_TOKEN", value: config.whatsappWebhookVerifyToken },
  ];

  const fastapiEnv = [
    { name: "API_URL", value: apiBaseUrl },
    { name: "FASTAPI_PORT", value: "8001" },
    { name: "CELERY_BROKER_URL", value: celeryBrokerUrl },
    { name: "REDIS_NOTIFICATIONS_URL", value: redisNotificationsUrl },
    { name: "CORS_ORIGINS", value: config.corsOrigins },
    { name: "FRONTEND_URL", value: frontendUrl },
  ];

  const djangoTaskDefinition = new aws.ecs.TaskDefinition("django-task", {
    family: `${config.namePrefix}-django`,
    networkMode: "awsvpc",
    requiresCompatibilities: ["EC2"],
    executionRoleArn: args.taskExecutionRole.arn,
    taskRoleArn: args.taskRole.arn,
    cpu: "1024",
    memory: "2048",
    containerDefinitions: pulumi.jsonStringify([{
      name: "django",
      image: pulumi.interpolate`${args.djangoRepo.repositoryUrl}:${config.djangoImageTag}`,
      essential: true,
      portMappings: [{ containerPort: 8000, hostPort: 8000, protocol: "tcp" }],
      command: ["python", "manage.py", "runserver", "0.0.0.0:8000"],
      environment: djangoEnv,
      logConfiguration: {
        logDriver: "awslogs",
        options: {
          "awslogs-group": args.appLogs.name,
          "awslogs-region": args.region.name,
          "awslogs-stream-prefix": "django",
        },
      },
    }]),
    tags: args.tags,
  });

  const djangoMigrateTaskDefinition = new aws.ecs.TaskDefinition("django-migrate-task", {
    family: `${config.namePrefix}-django-migrate`,
    networkMode: "awsvpc",
    requiresCompatibilities: ["EC2"],
    executionRoleArn: args.taskExecutionRole.arn,
    taskRoleArn: args.taskRole.arn,
    cpu: "512",
    memory: "1024",
    containerDefinitions: pulumi.jsonStringify([{
      name: "django-migrate",
      image: pulumi.interpolate`${args.djangoRepo.repositoryUrl}:${config.djangoImageTag}`,
      essential: true,
      command: ["python", "manage.py", "migrate"],
      environment: djangoEnv,
      logConfiguration: {
        logDriver: "awslogs",
        options: {
          "awslogs-group": args.appLogs.name,
          "awslogs-region": args.region.name,
          "awslogs-stream-prefix": "django-migrate",
        },
      },
    }]),
    tags: args.tags,
  });

  const fastapiTaskDefinition = new aws.ecs.TaskDefinition("fastapi-task", {
    family: `${config.namePrefix}-fastapi`,
    networkMode: "awsvpc",
    requiresCompatibilities: ["EC2"],
    executionRoleArn: args.taskExecutionRole.arn,
    taskRoleArn: args.taskRole.arn,
    cpu: "512",
    memory: "1024",
    containerDefinitions: pulumi.jsonStringify([{
      name: "fastapi",
      image: pulumi.interpolate`${args.streamingRepo.repositoryUrl}:${config.streamingImageTag}`,
      essential: true,
      portMappings: [{ containerPort: 8001, hostPort: 8001, protocol: "tcp" }],
      command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"],
      environment: fastapiEnv,
      logConfiguration: {
        logDriver: "awslogs",
        options: {
          "awslogs-group": args.appLogs.name,
          "awslogs-region": args.region.name,
          "awslogs-stream-prefix": "fastapi",
        },
      },
    }]),
    tags: args.tags,
  });

  const celeryWorkerTaskDefinition = new aws.ecs.TaskDefinition("celery-worker-task", {
    family: `${config.namePrefix}-celery-worker`,
    networkMode: "awsvpc",
    requiresCompatibilities: ["EC2"],
    executionRoleArn: args.taskExecutionRole.arn,
    taskRoleArn: args.taskRole.arn,
    cpu: "1024",
    memory: "2048",
    containerDefinitions: pulumi.jsonStringify([{
      name: "celery-worker",
      image: pulumi.interpolate`${args.djangoRepo.repositoryUrl}:${config.djangoImageTag}`,
      essential: true,
      command: ["celery", "-A", "api.celery", "worker", "--pool=gevent", "--loglevel=INFO"],
      environment: djangoEnv,
      logConfiguration: {
        logDriver: "awslogs",
        options: {
          "awslogs-group": args.appLogs.name,
          "awslogs-region": args.region.name,
          "awslogs-stream-prefix": "celery-worker",
        },
      },
    }]),
    tags: args.tags,
  });

  const celeryBeatTaskDefinition = new aws.ecs.TaskDefinition("celery-beat-task", {
    family: `${config.namePrefix}-celery-beat`,
    networkMode: "awsvpc",
    requiresCompatibilities: ["EC2"],
    executionRoleArn: args.taskExecutionRole.arn,
    taskRoleArn: args.taskRole.arn,
    cpu: "256",
    memory: "512",
    containerDefinitions: pulumi.jsonStringify([{
      name: "celery-beat",
      image: pulumi.interpolate`${args.djangoRepo.repositoryUrl}:${config.djangoImageTag}`,
      essential: true,
      command: ["celery", "-A", "api.celery", "beat", "--loglevel=INFO"],
      environment: djangoEnv,
      logConfiguration: {
        logDriver: "awslogs",
        options: {
          "awslogs-group": args.appLogs.name,
          "awslogs-region": args.region.name,
          "awslogs-stream-prefix": "celery-beat",
        },
      },
    }]),
    tags: args.tags,
  });

  const chromaTaskDefinition = new aws.ecs.TaskDefinition("chroma-task", {
    family: `${config.namePrefix}-chroma`,
    networkMode: "awsvpc",
    requiresCompatibilities: ["EC2"],
    executionRoleArn: args.taskExecutionRole.arn,
    taskRoleArn: args.taskRole.arn,
    cpu: "512",
    memory: "1024",
    volumes: [{
      name: "chroma-data",
      efsVolumeConfiguration: {
        fileSystemId: args.chromaEfsId,
        transitEncryption: "ENABLED",
      },
    }],
    containerDefinitions: pulumi.jsonStringify([{
      name: "chroma",
      image: args.chromaImage,
      essential: true,
      portMappings: [{ containerPort: 8000, hostPort: 8000, protocol: "tcp" }],
      mountPoints: [{ sourceVolume: "chroma-data", containerPath: "/data", readOnly: false }],
      logConfiguration: {
        logDriver: "awslogs",
        options: {
          "awslogs-group": args.appLogs.name,
          "awslogs-region": args.region.name,
          "awslogs-stream-prefix": "chroma",
        },
      },
    }]),
    tags: args.tags,
  }, { dependsOn: args.chromaMountTargets });

  const serviceNetworkConfiguration = {
    subnets: args.publicSubnetIds,
    securityGroups: [args.appTasksSecurityGroupId],
  };

  const capacityProviderStrategies = [{ capacityProvider: args.capacityProvider.name, weight: 1, base: 1 }];

  const djangoService = new aws.ecs.Service("django-service", {
    name: `${config.namePrefix}-django`,
    cluster: args.cluster.arn,
    taskDefinition: djangoTaskDefinition.arn,
    desiredCount: config.djangoDesiredCount,
    networkConfiguration: serviceNetworkConfiguration,
    loadBalancers: [{ targetGroupArn: args.djangoTargetGroup.arn, containerName: "django", containerPort: 8000 }],
    capacityProviderStrategies,
    deploymentMinimumHealthyPercent: 50,
    deploymentMaximumPercent: 200,
    waitForSteadyState: false,
    tags: args.tags,
  }, { dependsOn: [args.clusterCapacityProviders, args.httpListener] });

  const fastapiService = new aws.ecs.Service("fastapi-service", {
    name: `${config.namePrefix}-fastapi`,
    cluster: args.cluster.arn,
    taskDefinition: fastapiTaskDefinition.arn,
    desiredCount: config.fastapiDesiredCount,
    networkConfiguration: serviceNetworkConfiguration,
    loadBalancers: [{ targetGroupArn: args.fastapiTargetGroup.arn, containerName: "fastapi", containerPort: 8001 }],
    capacityProviderStrategies,
    deploymentMinimumHealthyPercent: 50,
    deploymentMaximumPercent: 200,
    waitForSteadyState: false,
    tags: args.tags,
  }, { dependsOn: [args.clusterCapacityProviders, args.httpListener] });

  const celeryWorkerService = new aws.ecs.Service("celery-worker-service", {
    name: `${config.namePrefix}-celery-worker`,
    cluster: args.cluster.arn,
    taskDefinition: celeryWorkerTaskDefinition.arn,
    desiredCount: config.celeryWorkerDesiredCount,
    networkConfiguration: serviceNetworkConfiguration,
    capacityProviderStrategies,
    waitForSteadyState: false,
    tags: args.tags,
  }, { dependsOn: [args.clusterCapacityProviders] });

  const celeryBeatService = new aws.ecs.Service("celery-beat-service", {
    name: `${config.namePrefix}-celery-beat`,
    cluster: args.cluster.arn,
    taskDefinition: celeryBeatTaskDefinition.arn,
    desiredCount: config.celeryBeatDesiredCount,
    networkConfiguration: serviceNetworkConfiguration,
    capacityProviderStrategies,
    waitForSteadyState: false,
    tags: args.tags,
  }, { dependsOn: [args.clusterCapacityProviders] });

  const chromaService = new aws.ecs.Service("chroma-service", {
    name: `${config.namePrefix}-chroma`,
    cluster: args.cluster.arn,
    taskDefinition: chromaTaskDefinition.arn,
    desiredCount: config.chromaDesiredCount,
    networkConfiguration: serviceNetworkConfiguration,
    capacityProviderStrategies,
    serviceRegistries: { registryArn: args.chromaDiscoveryServiceArn },
    waitForSteadyState: false,
    tags: args.tags,
  }, { dependsOn: [args.clusterCapacityProviders, ...args.chromaMountTargets] });

  return {
    djangoMigrateTaskDefinition,
    djangoService,
    fastapiService,
    celeryWorkerService,
    celeryBeatService,
    chromaService,
  };
}

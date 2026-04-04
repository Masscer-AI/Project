import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { AppConfig, Tags } from "./config";
import { ProviderParameterArns } from "./parameter-store";

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
  appBaseUrl: pulumi.Input<string>;
  coreBaseUrl: pulumi.Input<string>;
  djangoTargetGroup: aws.lb.TargetGroup;
  fastapiTargetGroup: aws.lb.TargetGroup;
  httpListener: aws.lb.Listener;
  appTasksSecurityGroupId: any;
  privateSubnetIds: any[];
  chromaImage: string;
  chromaEfsId: any;
  chromaMountTargets: aws.efs.MountTarget[];
  chromaDiscoveryServiceArn: any;
  chromaInternalHost: pulumi.Output<string>;
  providerParameterArns: ProviderParameterArns;
  mediaBucket: aws.s3.BucketV2;
}) {
  const { config } = args;

  const dbConnectionString = pulumi.interpolate`postgres://${config.dbUsername}:${config.dbPassword}@${args.postgres.address}:${args.postgres.port}/${config.dbName}`;
  const redisBaseUrl = pulumi.interpolate`redis://${args.redis.primaryEndpointAddress}:${args.redis.port}`;
  const celeryBrokerUrl = pulumi.interpolate`${redisBaseUrl}/0`;
  const redisCacheUrl = pulumi.interpolate`${redisBaseUrl}/1`;
  const redisNotificationsUrl = pulumi.interpolate`${redisBaseUrl}/2`;
  const frontendUrl = pulumi.output(args.appBaseUrl);
  const apiBaseUrl = pulumi.output(args.coreBaseUrl);
  const djangoAllowedHosts = pulumi
    .all([args.alb.dnsName, config.appDomain, config.coreDomain])
    .apply(([albDnsName, appDomain, coreDomain]) => {
      const hosts = [albDnsName, appDomain, coreDomain]
        .map((v) => (v ?? "").trim())
        .filter(Boolean);
      if (config.allowedExtraHosts.trim()) {
        hosts.push(...config.allowedExtraHosts.split(",").map((h) => h.trim()).filter(Boolean));
      }
      return Array.from(new Set(hosts)).join(",");
    });

  // Grant the ECS task role read/write access to the media S3 bucket.
  new aws.iam.RolePolicy("ecs-task-s3-media-policy", {
    role: args.taskRole.name,
    policy: args.mediaBucket.arn.apply((arn) => JSON.stringify({
      Version: "2012-10-17",
      Statement: [{
        Effect: "Allow",
        Action: ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"],
        Resource: [arn, `${arn}/*`],
      }],
    })),
  });

  const djangoEnv = [
    { name: "DB_CONNECTION_STRING", value: dbConnectionString },
    { name: "SECRET_KEY", value: config.djangoSecretKey },
    { name: "CELERY_BROKER_URL", value: celeryBrokerUrl },
    { name: "CELERY_RESULT_BACKEND", value: celeryBrokerUrl },
    { name: "REDIS_CACHE_URL", value: redisCacheUrl },
    { name: "REDIS_NOTIFICATIONS_URL", value: redisNotificationsUrl },
    { name: "CHROMA_HOST", value: args.chromaInternalHost },
    { name: "CHROMA_PORT", value: "8000" },
    { name: "API_BASE_URL", value: apiBaseUrl },
    { name: "FRONTEND_URL", value: frontendUrl },
    { name: "ALLOWED_EXTRA_HOSTS", value: djangoAllowedHosts },
    { name: "AWS_STORAGE_BUCKET_NAME", value: args.mediaBucket.bucket },
    { name: "AWS_S3_REGION_NAME", value: args.region.name },
  ];

  const providerSecrets = [
    { name: "OPENAI_API_KEY", valueFrom: args.providerParameterArns.openAiApiKeyArn },
    { name: "ANTHROPIC_API_KEY", valueFrom: args.providerParameterArns.anthropicApiKeyArn },
    { name: "XAI_API_KEY", valueFrom: args.providerParameterArns.xaiApiKeyArn },
    { name: "PEXELS_API_KEY", valueFrom: args.providerParameterArns.pexelsApiKeyArn },
    { name: "FIRECRAWL_API_KEY", valueFrom: args.providerParameterArns.firecrawlApiKeyArn },
    { name: "BFL_API_KEY", valueFrom: args.providerParameterArns.bflApiKeyArn },
    { name: "RUNWAY_API_KEY", valueFrom: args.providerParameterArns.runwayApiKeyArn },
    { name: "RESEND_API_KEY", valueFrom: args.providerParameterArns.resendApiKeyArn },
    { name: "WHATSAPP_GRAPH_API_TOKEN", valueFrom: args.providerParameterArns.whatsappGraphApiTokenArn },
    { name: "WHATSAPP_WEBHOOK_VERIFY_TOKEN", valueFrom: args.providerParameterArns.whatsappWebhookVerifyTokenArn },
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
      // Ensure admin/static assets exist when DEBUG=false in production.
      command: ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py runserver 0.0.0.0:8000"],
      environment: djangoEnv,
      secrets: providerSecrets,
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
      secrets: providerSecrets,
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
      secrets: providerSecrets,
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
      secrets: providerSecrets,
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
    // Run tasks in private subnets; NAT gateway provides outbound internet access.
    subnets: args.privateSubnetIds,
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
    // Celery has no ALB health checks, and desiredCount is typically 1.
    // Default ECS rolling deploy (minHealthy=100, max=200) tries to run 2 tasks briefly,
    // which often fails with RESOURCE:MEMORY on small clusters. Use stop-then-start.
    deploymentMinimumHealthyPercent: 0,
    deploymentMaximumPercent: 100,
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
    deploymentMinimumHealthyPercent: 0,
    deploymentMaximumPercent: 100,
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
    djangoTaskDefinition,
    djangoService,
    fastapiService,
    celeryWorkerService,
    celeryBeatService,
    chromaService,
  };
}

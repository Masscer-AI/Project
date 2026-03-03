import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

const cfg = new pulumi.Config();
const environment = cfg.get("environment") ?? pulumi.getStack();
const namePrefix = cfg.get("namePrefix") ?? `masscer-${environment}`;
const instanceType = cfg.get("instanceType") ?? "t3.medium";
const asgMinSize = cfg.getNumber("asgMinSize") ?? 1;
const asgDesiredSize = cfg.getNumber("asgDesiredSize") ?? 1;
const asgMaxSize = cfg.getNumber("asgMaxSize") ?? 2;
const djangoDesiredCount = cfg.getNumber("djangoDesiredCount") ?? 1;
const fastapiDesiredCount = cfg.getNumber("fastapiDesiredCount") ?? 1;
const celeryWorkerDesiredCount = cfg.getNumber("celeryWorkerDesiredCount") ?? 1;
const celeryBeatDesiredCount = cfg.getNumber("celeryBeatDesiredCount") ?? 1;
const chromaDesiredCount = cfg.getNumber("chromaDesiredCount") ?? 1;

const dbName = cfg.get("dbName") ?? "masscer";
const dbUsername = cfg.get("dbUsername") ?? "masscer";
const dbPassword = cfg.requireSecret("dbPassword");
const djangoSecretKey = cfg.requireSecret("djangoSecretKey");

const djangoImageTag = cfg.get("djangoImageTag") ?? "latest";
const streamingImageTag = cfg.get("streamingImageTag") ?? "latest";
const chromaImage = cfg.get("chromaImage") ?? "chromadb/chroma:0.5.11";

const corsOrigins = cfg.get("corsOrigins") ?? "*";
const allowedExtraHosts = cfg.get("allowedExtraHosts") ?? "";

const openAiApiKey = cfg.getSecret("openAiApiKey") ?? pulumi.output("");
const anthropicApiKey = cfg.getSecret("anthropicApiKey") ?? pulumi.output("");
const xaiApiKey = cfg.getSecret("xaiApiKey") ?? pulumi.output("");
const pexelsApiKey = cfg.getSecret("pexelsApiKey") ?? pulumi.output("");
const braveApiKey = cfg.getSecret("braveApiKey") ?? pulumi.output("");
const bflApiKey = cfg.getSecret("bflApiKey") ?? pulumi.output("");
const runwayApiKey = cfg.getSecret("runwayApiKey") ?? pulumi.output("");
const whatsappGraphApiToken = cfg.getSecret("whatsappGraphApiToken") ?? pulumi.output("");
const whatsappWebhookVerifyToken = cfg.getSecret("whatsappWebhookVerifyToken") ?? pulumi.output("");

const tags: Record<string, string> = {
  Project: "masscer",
  Environment: environment,
  ManagedBy: "pulumi",
};

function secureBucket(resourceName: string, bucketName: string) {
  const bucket = new aws.s3.BucketV2(resourceName, {
    bucket: bucketName,
    tags,
  });

  new aws.s3.BucketServerSideEncryptionConfigurationV2(`${resourceName}-encryption`, {
    bucket: bucket.id,
    rules: [{
      applyServerSideEncryptionByDefault: {
        sseAlgorithm: "AES256",
      },
    }],
  });

  new aws.s3.BucketVersioningV2(`${resourceName}-versioning`, {
    bucket: bucket.id,
    versioningConfiguration: { status: "Enabled" },
  });

  new aws.s3.BucketPublicAccessBlock(`${resourceName}-public-access`, {
    bucket: bucket.id,
    blockPublicAcls: true,
    blockPublicPolicy: true,
    ignorePublicAcls: true,
    restrictPublicBuckets: true,
  });

  return bucket;
}

const staticBucket = secureBucket("static-assets-bucket", `${namePrefix}-static-assets`);
const mediaBucket = secureBucket("media-assets-bucket", `${namePrefix}-media-assets`);

const djangoRepo = new aws.ecr.Repository("django-repo", {
  name: `${namePrefix}-django`,
  imageTagMutability: "MUTABLE",
  forceDelete: true,
  tags,
});

const streamingRepo = new aws.ecr.Repository("streaming-repo", {
  name: `${namePrefix}-streaming`,
  imageTagMutability: "MUTABLE",
  forceDelete: true,
  tags,
});

const lifecyclePolicy = JSON.stringify({
  rules: [
    {
      rulePriority: 1,
      description: "Keep last 15 images",
      selection: {
        tagStatus: "any",
        countType: "imageCountMoreThan",
        countNumber: 15,
      },
      action: { type: "expire" },
    },
  ],
});

new aws.ecr.LifecyclePolicy("django-repo-policy", {
  repository: djangoRepo.name,
  policy: lifecyclePolicy,
});

new aws.ecr.LifecyclePolicy("streaming-repo-policy", {
  repository: streamingRepo.name,
  policy: lifecyclePolicy,
});

const cluster = new aws.ecs.Cluster("masscer-cluster", {
  name: `${namePrefix}-cluster`,
  settings: [{ name: "containerInsights", value: "enabled" }],
  tags,
});

const appLogs = new aws.cloudwatch.LogGroup("application-logs", {
  name: `/ecs/${namePrefix}`,
  retentionInDays: 30,
  tags,
});

const defaultVpc = aws.ec2.getVpcOutput({ default: true });
const defaultSubnets = aws.ec2.getSubnetsOutput({
  filters: [{
    name: "vpc-id",
    values: [defaultVpc.id],
  }],
});
const region = aws.getRegionOutput();

const ecsInstanceRole = new aws.iam.Role("ecs-instance-role", {
  name: `${namePrefix}-ecs-instance-role`,
  assumeRolePolicy: aws.iam.assumeRolePolicyForPrincipal({ Service: "ec2.amazonaws.com" }),
  tags,
});

new aws.iam.RolePolicyAttachment("ecs-instance-ecs-policy", {
  role: ecsInstanceRole.name,
  policyArn: "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role",
});

new aws.iam.RolePolicyAttachment("ecs-instance-ssm-policy", {
  role: ecsInstanceRole.name,
  policyArn: "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
});

const ecsInstanceProfile = new aws.iam.InstanceProfile("ecs-instance-profile", {
  name: `${namePrefix}-ecs-instance-profile`,
  role: ecsInstanceRole.name,
  tags,
});

const ecsNodeSg = new aws.ec2.SecurityGroup("ecs-node-sg", {
  name: `${namePrefix}-ecs-node-sg`,
  description: "Security group for ECS EC2 container instances",
  vpcId: defaultVpc.id,
  egress: [{
    protocol: "-1",
    fromPort: 0,
    toPort: 0,
    cidrBlocks: ["0.0.0.0/0"],
  }],
  tags,
});

const ecsAmiId = aws.ssm.getParameterOutput({
  name: "/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id",
});

const launchTemplate = new aws.ec2.LaunchTemplate("ecs-launch-template", {
  namePrefix: `${namePrefix}-ecs-`,
  imageId: ecsAmiId.value,
  instanceType,
  iamInstanceProfile: {
    arn: ecsInstanceProfile.arn,
  },
  vpcSecurityGroupIds: [ecsNodeSg.id],
  userData: pulumi.interpolate`#!/bin/bash
echo ECS_CLUSTER=${cluster.name} >> /etc/ecs/ecs.config
`,
  monitoring: {
    enabled: true,
  },
  tagSpecifications: [{
    resourceType: "instance",
    tags: {
      ...tags,
      Name: `${namePrefix}-ecs-node`,
    },
  }],
  tags,
});

const ecsAsg = new aws.autoscaling.Group("ecs-asg", {
  name: `${namePrefix}-ecs-asg`,
  desiredCapacity: asgDesiredSize,
  minSize: asgMinSize,
  maxSize: asgMaxSize,
  vpcZoneIdentifiers: defaultSubnets.ids,
  healthCheckType: "EC2",
  launchTemplate: {
    id: launchTemplate.id,
    version: "$Latest",
  },
  tags: [
    { key: "Name", value: `${namePrefix}-ecs-node`, propagateAtLaunch: true },
    { key: "Project", value: tags.Project, propagateAtLaunch: true },
    { key: "Environment", value: tags.Environment, propagateAtLaunch: true },
    { key: "ManagedBy", value: tags.ManagedBy, propagateAtLaunch: true },
  ],
});

const capacityProvider = new aws.ecs.CapacityProvider("ecs-ec2-capacity-provider", {
  name: `${namePrefix}-ec2-cp`,
  autoScalingGroupProvider: {
    autoScalingGroupArn: ecsAsg.arn,
    managedTerminationProtection: "DISABLED",
    managedScaling: {
      status: "ENABLED",
      targetCapacity: 80,
      minimumScalingStepSize: 1,
      maximumScalingStepSize: 2,
    },
  },
  tags,
});

const clusterCapacityProviders = new aws.ecs.ClusterCapacityProviders("cluster-capacity-providers", {
  clusterName: cluster.name,
  capacityProviders: [capacityProvider.name],
  defaultCapacityProviderStrategies: [{
    capacityProvider: capacityProvider.name,
    weight: 1,
    base: 1,
  }],
});

const albSg = new aws.ec2.SecurityGroup("alb-sg", {
  name: `${namePrefix}-alb-sg`,
  description: "Public ALB security group",
  vpcId: defaultVpc.id,
  ingress: [
    {
      protocol: "tcp",
      fromPort: 80,
      toPort: 80,
      cidrBlocks: ["0.0.0.0/0"],
      description: "Public HTTP ingress",
    },
    {
      protocol: "tcp",
      fromPort: 443,
      toPort: 443,
      cidrBlocks: ["0.0.0.0/0"],
      description: "Public HTTPS ingress",
    },
  ],
  egress: [{
    protocol: "-1",
    fromPort: 0,
    toPort: 0,
    cidrBlocks: ["0.0.0.0/0"],
  }],
  tags,
});

const appTasksSg = new aws.ec2.SecurityGroup("app-tasks-sg", {
  name: `${namePrefix}-app-tasks-sg`,
  description: "Security group for ECS app tasks",
  vpcId: defaultVpc.id,
  ingress: [
    {
      protocol: "tcp",
      fromPort: 8000,
      toPort: 8001,
      securityGroups: [albSg.id],
      description: "ALB traffic to Django/FastAPI services",
    },
    {
      protocol: "tcp",
      fromPort: 8000,
      toPort: 8000,
      self: true,
      description: "Internal task traffic to Chroma",
    },
  ],
  egress: [{
    protocol: "-1",
    fromPort: 0,
    toPort: 0,
    cidrBlocks: ["0.0.0.0/0"],
  }],
  tags,
});

const databaseSg = new aws.ec2.SecurityGroup("database-sg", {
  name: `${namePrefix}-database-sg`,
  description: "Security group for RDS PostgreSQL",
  vpcId: defaultVpc.id,
  ingress: [{
    protocol: "tcp",
    fromPort: 5432,
    toPort: 5432,
    securityGroups: [appTasksSg.id],
    description: "ECS app tasks to PostgreSQL",
  }],
  egress: [{
    protocol: "-1",
    fromPort: 0,
    toPort: 0,
    cidrBlocks: ["0.0.0.0/0"],
  }],
  tags,
});

const redisSg = new aws.ec2.SecurityGroup("redis-sg", {
  name: `${namePrefix}-redis-sg`,
  description: "Security group for ElastiCache Redis",
  vpcId: defaultVpc.id,
  ingress: [{
    protocol: "tcp",
    fromPort: 6379,
    toPort: 6379,
    securityGroups: [appTasksSg.id],
    description: "ECS app tasks to Redis",
  }],
  egress: [{
    protocol: "-1",
    fromPort: 0,
    toPort: 0,
    cidrBlocks: ["0.0.0.0/0"],
  }],
  tags,
});

const efsSg = new aws.ec2.SecurityGroup("efs-sg", {
  name: `${namePrefix}-efs-sg`,
  description: "Security group for Chroma EFS storage",
  vpcId: defaultVpc.id,
  ingress: [{
    protocol: "tcp",
    fromPort: 2049,
    toPort: 2049,
    securityGroups: [appTasksSg.id],
    description: "ECS app tasks to EFS mount target",
  }],
  egress: [{
    protocol: "-1",
    fromPort: 0,
    toPort: 0,
    cidrBlocks: ["0.0.0.0/0"],
  }],
  tags,
});

const dbSubnetGroup = new aws.rds.SubnetGroup("db-subnet-group", {
  name: `${namePrefix}-db-subnets`,
  subnetIds: defaultSubnets.ids,
  tags,
});

const redisSubnetGroup = new aws.elasticache.SubnetGroup("redis-subnet-group", {
  name: `${namePrefix}-redis-subnets`,
  subnetIds: defaultSubnets.ids,
});

const postgres = new aws.rds.Instance("postgres", {
  identifier: `${namePrefix}-postgres`,
  allocatedStorage: 20,
  engine: "postgres",
  engineVersion: "15.7",
  instanceClass: "db.t4g.medium",
  dbName,
  username: dbUsername,
  password: dbPassword,
  dbSubnetGroupName: dbSubnetGroup.name,
  vpcSecurityGroupIds: [databaseSg.id],
  skipFinalSnapshot: true,
  publiclyAccessible: false,
  storageEncrypted: true,
  deletionProtection: false,
  tags,
});

const redis = new aws.elasticache.ReplicationGroup("redis", {
  replicationGroupId: `${namePrefix}-redis`,
  description: `Redis for ${namePrefix}`,
  engine: "redis",
  engineVersion: "7.1",
  nodeType: "cache.t3.micro",
  numCacheClusters: 1,
  port: 6379,
  parameterGroupName: "default.redis7",
  automaticFailoverEnabled: false,
  subnetGroupName: redisSubnetGroup.name,
  securityGroupIds: [redisSg.id],
  tags,
});

const chromaEfs = new aws.efs.FileSystem("chroma-efs", {
  creationToken: `${namePrefix}-chroma`,
  encrypted: true,
  tags: {
    ...tags,
    Name: `${namePrefix}-chroma-efs`,
  },
});

const firstSubnetId = defaultSubnets.ids.apply((ids) => ids[0]);
const chromaMountTarget = new aws.efs.MountTarget("chroma-efs-mount-target", {
  fileSystemId: chromaEfs.id,
  subnetId: firstSubnetId,
  securityGroups: [efsSg.id],
});

const alb = new aws.lb.LoadBalancer("app-alb", {
  name: `${namePrefix}-alb`,
  internal: false,
  loadBalancerType: "application",
  securityGroups: [albSg.id],
  subnets: defaultSubnets.ids,
  tags,
});

const djangoTargetGroup = new aws.lb.TargetGroup("django-tg", {
  name: `${namePrefix}-django`,
  port: 8000,
  protocol: "HTTP",
  targetType: "ip",
  vpcId: defaultVpc.id,
  healthCheck: {
    path: "/admin/login/",
    matcher: "200-399",
    interval: 30,
    timeout: 5,
    healthyThreshold: 2,
    unhealthyThreshold: 3,
  },
  tags,
});

const fastapiTargetGroup = new aws.lb.TargetGroup("fastapi-tg", {
  name: `${namePrefix}-fastapi`,
  port: 8001,
  protocol: "HTTP",
  targetType: "ip",
  vpcId: defaultVpc.id,
  healthCheck: {
    path: "/",
    matcher: "200-399",
    interval: 30,
    timeout: 5,
    healthyThreshold: 2,
    unhealthyThreshold: 3,
  },
  tags,
});

const httpListener = new aws.lb.Listener("http-listener", {
  loadBalancerArn: alb.arn,
  port: 80,
  protocol: "HTTP",
  defaultActions: [{
    type: "forward",
    targetGroupArn: fastapiTargetGroup.arn,
  }],
  tags,
});

new aws.lb.ListenerRule("django-path-rules", {
  listenerArn: httpListener.arn,
  priority: 10,
  actions: [{
    type: "forward",
    targetGroupArn: djangoTargetGroup.arn,
  }],
  conditions: [{
    pathPattern: {
      values: ["/v1/*", "/admin/*", "/static/*", "/media/*"],
    },
  }],
  tags,
});

new aws.lb.ListenerRule("socketio-path-rule", {
  listenerArn: httpListener.arn,
  priority: 20,
  actions: [{
    type: "forward",
    targetGroupArn: fastapiTargetGroup.arn,
  }],
  conditions: [{
    pathPattern: {
      values: ["/socket.io/*"],
    },
  }],
  tags,
});

const taskExecutionRole = new aws.iam.Role("ecs-task-execution-role", {
  name: `${namePrefix}-ecs-task-exec-role`,
  assumeRolePolicy: aws.iam.assumeRolePolicyForPrincipal({ Service: "ecs-tasks.amazonaws.com" }),
  tags,
});

new aws.iam.RolePolicyAttachment("ecs-task-exec-policy", {
  role: taskExecutionRole.name,
  policyArn: "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
});

const taskRole = new aws.iam.Role("ecs-task-role", {
  name: `${namePrefix}-ecs-task-role`,
  assumeRolePolicy: aws.iam.assumeRolePolicyForPrincipal({ Service: "ecs-tasks.amazonaws.com" }),
  tags,
});

const dbConnectionString = pulumi.interpolate`postgres://${dbUsername}:${dbPassword}@${postgres.address}:${postgres.port}/${dbName}`;
const redisBaseUrl = pulumi.interpolate`redis://${redis.primaryEndpointAddress}:${redis.port}`;
const celeryBrokerUrl = pulumi.interpolate`${redisBaseUrl}/0`;
const redisCacheUrl = pulumi.interpolate`${redisBaseUrl}/1`;
const redisNotificationsUrl = pulumi.interpolate`${redisBaseUrl}/2`;
const frontendUrl = pulumi.interpolate`http://${alb.dnsName}`;
const apiBaseUrl = pulumi.interpolate`http://${alb.dnsName}`;
const djangoAllowedHosts = pulumi.interpolate`${alb.dnsName}${allowedExtraHosts ? `,${allowedExtraHosts}` : ""}`;
const serviceDiscoveryNamespaceName = `${namePrefix}.internal`;
const chromaInternalHost = pulumi.interpolate`chroma.${serviceDiscoveryNamespaceName}`;

const privateNamespace = new aws.servicediscovery.PrivateDnsNamespace("private-namespace", {
  name: serviceDiscoveryNamespaceName,
  vpc: defaultVpc.id,
  description: `Private namespace for ${namePrefix} ECS services`,
  tags,
});

const chromaDiscoveryService = new aws.servicediscovery.Service("chroma-discovery-service", {
  name: "chroma",
  dnsConfig: {
    namespaceId: privateNamespace.id,
    dnsRecords: [{
      ttl: 10,
      type: "A",
    }],
    routingPolicy: "MULTIVALUE",
  },
  healthCheckCustomConfig: {
    failureThreshold: 1,
  },
  tags,
});

const djangoEnv = [
  { name: "DB_CONNECTION_STRING", value: dbConnectionString },
  { name: "SECRET_KEY", value: djangoSecretKey },
  { name: "CELERY_BROKER_URL", value: celeryBrokerUrl },
  { name: "CELERY_RESULT_BACKEND", value: celeryBrokerUrl },
  { name: "REDIS_CACHE_URL", value: redisCacheUrl },
  { name: "REDIS_NOTIFICATIONS_URL", value: redisNotificationsUrl },
  { name: "MEDIA_ROOT", value: "/app/storage" },
  { name: "CHROMA_HOST", value: chromaInternalHost },
  { name: "CHROMA_PORT", value: "8000" },
  { name: "API_BASE_URL", value: apiBaseUrl },
  { name: "ALLOWED_EXTRA_HOSTS", value: djangoAllowedHosts },
  { name: "OPENAI_API_KEY", value: openAiApiKey },
  { name: "ANTHROPIC_API_KEY", value: anthropicApiKey },
  { name: "XAI_API_KEY", value: xaiApiKey },
  { name: "PEXELS_API_KEY", value: pexelsApiKey },
  { name: "BRAVE_API_KEY", value: braveApiKey },
  { name: "BFL_API_KEY", value: bflApiKey },
  { name: "RUNWAY_API_KEY", value: runwayApiKey },
  { name: "WHATSAPP_GRAPH_API_TOKEN", value: whatsappGraphApiToken },
  { name: "WHATSAPP_WEBHOOK_VERIFY_TOKEN", value: whatsappWebhookVerifyToken },
];

const fastapiEnv = [
  { name: "API_URL", value: apiBaseUrl },
  { name: "FASTAPI_PORT", value: "8001" },
  { name: "CELERY_BROKER_URL", value: celeryBrokerUrl },
  { name: "REDIS_NOTIFICATIONS_URL", value: redisNotificationsUrl },
  { name: "CORS_ORIGINS", value: corsOrigins },
  { name: "FRONTEND_URL", value: frontendUrl },
];

const djangoTaskDefinition = new aws.ecs.TaskDefinition("django-task", {
  family: `${namePrefix}-django`,
  networkMode: "awsvpc",
  requiresCompatibilities: ["EC2"],
  executionRoleArn: taskExecutionRole.arn,
  taskRoleArn: taskRole.arn,
  cpu: "1024",
  memory: "2048",
  containerDefinitions: pulumi.jsonStringify([{
    name: "django",
    image: pulumi.interpolate`${djangoRepo.repositoryUrl}:${djangoImageTag}`,
    essential: true,
    portMappings: [{ containerPort: 8000, hostPort: 8000, protocol: "tcp" }],
    command: ["python", "manage.py", "runserver", "0.0.0.0:8000"],
    environment: djangoEnv,
    logConfiguration: {
      logDriver: "awslogs",
      options: {
        "awslogs-group": appLogs.name,
        "awslogs-region": region.name,
        "awslogs-stream-prefix": "django",
      },
    },
  }]),
  tags,
});

const djangoMigrateTaskDefinition = new aws.ecs.TaskDefinition("django-migrate-task", {
  family: `${namePrefix}-django-migrate`,
  networkMode: "awsvpc",
  requiresCompatibilities: ["EC2"],
  executionRoleArn: taskExecutionRole.arn,
  taskRoleArn: taskRole.arn,
  cpu: "512",
  memory: "1024",
  containerDefinitions: pulumi.jsonStringify([{
    name: "django-migrate",
    image: pulumi.interpolate`${djangoRepo.repositoryUrl}:${djangoImageTag}`,
    essential: true,
    command: ["python", "manage.py", "migrate"],
    environment: djangoEnv,
    logConfiguration: {
      logDriver: "awslogs",
      options: {
        "awslogs-group": appLogs.name,
        "awslogs-region": region.name,
        "awslogs-stream-prefix": "django-migrate",
      },
    },
  }]),
  tags,
});

const fastapiTaskDefinition = new aws.ecs.TaskDefinition("fastapi-task", {
  family: `${namePrefix}-fastapi`,
  networkMode: "awsvpc",
  requiresCompatibilities: ["EC2"],
  executionRoleArn: taskExecutionRole.arn,
  taskRoleArn: taskRole.arn,
  cpu: "512",
  memory: "1024",
  containerDefinitions: pulumi.jsonStringify([{
    name: "fastapi",
    image: pulumi.interpolate`${streamingRepo.repositoryUrl}:${streamingImageTag}`,
    essential: true,
    portMappings: [{ containerPort: 8001, hostPort: 8001, protocol: "tcp" }],
    command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"],
    environment: fastapiEnv,
    logConfiguration: {
      logDriver: "awslogs",
      options: {
        "awslogs-group": appLogs.name,
        "awslogs-region": region.name,
        "awslogs-stream-prefix": "fastapi",
      },
    },
  }]),
  tags,
});

const celeryWorkerTaskDefinition = new aws.ecs.TaskDefinition("celery-worker-task", {
  family: `${namePrefix}-celery-worker`,
  networkMode: "awsvpc",
  requiresCompatibilities: ["EC2"],
  executionRoleArn: taskExecutionRole.arn,
  taskRoleArn: taskRole.arn,
  cpu: "1024",
  memory: "2048",
  containerDefinitions: pulumi.jsonStringify([{
    name: "celery-worker",
    image: pulumi.interpolate`${djangoRepo.repositoryUrl}:${djangoImageTag}`,
    essential: true,
    command: ["celery", "-A", "api.celery", "worker", "--pool=gevent", "--loglevel=INFO"],
    environment: djangoEnv,
    logConfiguration: {
      logDriver: "awslogs",
      options: {
        "awslogs-group": appLogs.name,
        "awslogs-region": region.name,
        "awslogs-stream-prefix": "celery-worker",
      },
    },
  }]),
  tags,
});

const celeryBeatTaskDefinition = new aws.ecs.TaskDefinition("celery-beat-task", {
  family: `${namePrefix}-celery-beat`,
  networkMode: "awsvpc",
  requiresCompatibilities: ["EC2"],
  executionRoleArn: taskExecutionRole.arn,
  taskRoleArn: taskRole.arn,
  cpu: "256",
  memory: "512",
  containerDefinitions: pulumi.jsonStringify([{
    name: "celery-beat",
    image: pulumi.interpolate`${djangoRepo.repositoryUrl}:${djangoImageTag}`,
    essential: true,
    command: ["celery", "-A", "api.celery", "beat", "--loglevel=INFO"],
    environment: djangoEnv,
    logConfiguration: {
      logDriver: "awslogs",
      options: {
        "awslogs-group": appLogs.name,
        "awslogs-region": region.name,
        "awslogs-stream-prefix": "celery-beat",
      },
    },
  }]),
  tags,
});

const chromaTaskDefinition = new aws.ecs.TaskDefinition("chroma-task", {
  family: `${namePrefix}-chroma`,
  networkMode: "awsvpc",
  requiresCompatibilities: ["EC2"],
  executionRoleArn: taskExecutionRole.arn,
  taskRoleArn: taskRole.arn,
  cpu: "512",
  memory: "1024",
  volumes: [{
    name: "chroma-data",
    efsVolumeConfiguration: {
      fileSystemId: chromaEfs.id,
      transitEncryption: "ENABLED",
    },
  }],
  containerDefinitions: pulumi.jsonStringify([{
    name: "chroma",
    image: chromaImage,
    essential: true,
    portMappings: [{ containerPort: 8000, hostPort: 8000, protocol: "tcp" }],
    mountPoints: [{
      sourceVolume: "chroma-data",
      containerPath: "/data",
      readOnly: false,
    }],
    logConfiguration: {
      logDriver: "awslogs",
      options: {
        "awslogs-group": appLogs.name,
        "awslogs-region": region.name,
        "awslogs-stream-prefix": "chroma",
      },
    },
  }]),
  tags,
}, { dependsOn: [chromaMountTarget] });

const djangoService = new aws.ecs.Service("django-service", {
  name: `${namePrefix}-django`,
  cluster: cluster.arn,
  taskDefinition: djangoTaskDefinition.arn,
  desiredCount: djangoDesiredCount,
  networkConfiguration: {
    assignPublicIp: true,
    subnets: defaultSubnets.ids,
    securityGroups: [appTasksSg.id],
  },
  loadBalancers: [{
    targetGroupArn: djangoTargetGroup.arn,
    containerName: "django",
    containerPort: 8000,
  }],
  capacityProviderStrategies: [{
    capacityProvider: capacityProvider.name,
    weight: 1,
    base: 1,
  }],
  deploymentMinimumHealthyPercent: 50,
  deploymentMaximumPercent: 200,
  waitForSteadyState: false,
  tags,
}, { dependsOn: [clusterCapacityProviders, httpListener] });

const fastapiService = new aws.ecs.Service("fastapi-service", {
  name: `${namePrefix}-fastapi`,
  cluster: cluster.arn,
  taskDefinition: fastapiTaskDefinition.arn,
  desiredCount: fastapiDesiredCount,
  networkConfiguration: {
    assignPublicIp: true,
    subnets: defaultSubnets.ids,
    securityGroups: [appTasksSg.id],
  },
  loadBalancers: [{
    targetGroupArn: fastapiTargetGroup.arn,
    containerName: "fastapi",
    containerPort: 8001,
  }],
  capacityProviderStrategies: [{
    capacityProvider: capacityProvider.name,
    weight: 1,
    base: 1,
  }],
  deploymentMinimumHealthyPercent: 50,
  deploymentMaximumPercent: 200,
  waitForSteadyState: false,
  tags,
}, { dependsOn: [clusterCapacityProviders, httpListener] });

const celeryWorkerService = new aws.ecs.Service("celery-worker-service", {
  name: `${namePrefix}-celery-worker`,
  cluster: cluster.arn,
  taskDefinition: celeryWorkerTaskDefinition.arn,
  desiredCount: celeryWorkerDesiredCount,
  networkConfiguration: {
    assignPublicIp: true,
    subnets: defaultSubnets.ids,
    securityGroups: [appTasksSg.id],
  },
  capacityProviderStrategies: [{
    capacityProvider: capacityProvider.name,
    weight: 1,
    base: 1,
  }],
  waitForSteadyState: false,
  tags,
}, { dependsOn: [clusterCapacityProviders] });

const celeryBeatService = new aws.ecs.Service("celery-beat-service", {
  name: `${namePrefix}-celery-beat`,
  cluster: cluster.arn,
  taskDefinition: celeryBeatTaskDefinition.arn,
  desiredCount: celeryBeatDesiredCount,
  networkConfiguration: {
    assignPublicIp: true,
    subnets: defaultSubnets.ids,
    securityGroups: [appTasksSg.id],
  },
  capacityProviderStrategies: [{
    capacityProvider: capacityProvider.name,
    weight: 1,
    base: 1,
  }],
  waitForSteadyState: false,
  tags,
}, { dependsOn: [clusterCapacityProviders] });

const chromaService = new aws.ecs.Service("chroma-service", {
  name: `${namePrefix}-chroma`,
  cluster: cluster.arn,
  taskDefinition: chromaTaskDefinition.arn,
  desiredCount: chromaDesiredCount,
  networkConfiguration: {
    assignPublicIp: true,
    subnets: defaultSubnets.ids,
    securityGroups: [appTasksSg.id],
  },
  capacityProviderStrategies: [{
    capacityProvider: capacityProvider.name,
    weight: 1,
    base: 1,
  }],
  serviceRegistries: {
    registryArn: chromaDiscoveryService.arn,
  },
  waitForSteadyState: false,
  tags,
}, { dependsOn: [clusterCapacityProviders, chromaMountTarget] });

export const ecsClusterName = cluster.name;
export const ec2CapacityProviderName = capacityProvider.name;
export const ecsAutoScalingGroupName = ecsAsg.name;
export const ecsNodeSecurityGroupId = ecsNodeSg.id;
export const appTasksSecurityGroupId = appTasksSg.id;
export const subnetIds = defaultSubnets.ids;
export const appAlbDnsName = alb.dnsName;
export const appBaseUrl = pulumi.interpolate`http://${alb.dnsName}`;
export const djangoEcrRepositoryUrl = djangoRepo.repositoryUrl;
export const streamingEcrRepositoryUrl = streamingRepo.repositoryUrl;
export const staticBucketName = staticBucket.bucket;
export const mediaBucketName = mediaBucket.bucket;
export const logGroupName = appLogs.name;
export const postgresAddress = postgres.address;
export const redisPrimaryEndpoint = redis.primaryEndpointAddress;
export const djangoServiceName = djangoService.name;
export const fastapiServiceName = fastapiService.name;
export const celeryWorkerServiceName = celeryWorkerService.name;
export const celeryBeatServiceName = celeryBeatService.name;
export const chromaServiceName = chromaService.name;
export const djangoMigrateTaskDefinitionArn = djangoMigrateTaskDefinition.arn;

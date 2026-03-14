import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { loadConfig } from "./modules/config";
import { createNetworking } from "./modules/networking";
import { createArtifacts } from "./modules/artifacts";
import { createSecurityGroups } from "./modules/security-groups";
import { createEcsBase } from "./modules/ecs-base";
import { createDataServices } from "./modules/data-services";
import { createRouting } from "./modules/routing";
import { createChromaDiscovery } from "./modules/service-discovery";
import { createAppServices } from "./modules/ecs-services";
import { createProviderParameters } from "./modules/parameter-store";

const config = loadConfig();
const region = aws.getRegionOutput();

const artifacts = createArtifacts(config.namePrefix, config.tags);
const networking = createNetworking(config.namePrefix, config.tags, config.vpcCidr);
const securityGroups = createSecurityGroups(config.namePrefix, networking.vpc.id, config.tags);

const ecsBase = createEcsBase({
  namePrefix: config.namePrefix,
  tags: config.tags,
  instanceType: config.instanceType,
  asgMinSize: config.asgMinSize,
  asgDesiredSize: config.asgDesiredSize,
  asgMaxSize: config.asgMaxSize,
  publicSubnetIds: networking.publicSubnetIds,
  ecsNodeSecurityGroupId: securityGroups.ecsNodeSg.id,
});

const dataServices = createDataServices({
  namePrefix: config.namePrefix,
  tags: config.tags,
  dbName: config.dbName,
  dbUsername: config.dbUsername,
  dbPassword: config.dbPassword,
  privateSubnetIds: networking.privateSubnetIds,
  databaseSecurityGroupId: securityGroups.databaseSg.id,
  redisSecurityGroupId: securityGroups.redisSg.id,
  efsSecurityGroupId: securityGroups.efsSg.id,
});

const routing = createRouting({
  namePrefix: config.namePrefix,
  tags: config.tags,
  vpcId: networking.vpc.id,
  albSecurityGroupId: securityGroups.albSg.id,
  publicSubnetIds: networking.publicSubnetIds,
  rootDomain: config.rootDomain,
  appDomain: config.appDomain,
  coreDomain: config.coreDomain,
});

const discovery = createChromaDiscovery({
  namePrefix: config.namePrefix,
  tags: config.tags,
  vpcId: networking.vpc.id,
});

const parameterStore = createProviderParameters({
  namePrefix: config.namePrefix,
  openAiApiKey: config.openAiApiKey,
  anthropicApiKey: config.anthropicApiKey,
  xaiApiKey: config.xaiApiKey,
  pexelsApiKey: config.pexelsApiKey,
  braveApiKey: config.braveApiKey,
  bflApiKey: config.bflApiKey,
  runwayApiKey: config.runwayApiKey,
  whatsappGraphApiToken: config.whatsappGraphApiToken,
  whatsappWebhookVerifyToken: config.whatsappWebhookVerifyToken,
  taskExecutionRoleName: ecsBase.taskExecutionRole.name,
});

const services = createAppServices({
  config,
  tags: config.tags,
  region,
  appLogs: artifacts.appLogs,
  cluster: ecsBase.cluster,
  capacityProvider: ecsBase.capacityProvider,
  clusterCapacityProviders: ecsBase.clusterCapacityProviders,
  taskExecutionRole: ecsBase.taskExecutionRole,
  taskRole: ecsBase.taskRole,
  djangoRepo: artifacts.djangoRepo,
  streamingRepo: artifacts.streamingRepo,
  postgres: dataServices.postgres,
  redis: dataServices.redis,
  alb: routing.alb,
  appBaseUrl: routing.appBaseUrl,
  coreBaseUrl: routing.coreBaseUrl,
  djangoTargetGroup: routing.djangoTargetGroup,
  fastapiTargetGroup: routing.fastapiTargetGroup,
  httpListener: routing.httpListener,
  appTasksSecurityGroupId: securityGroups.appTasksSg.id,
  privateSubnetIds: networking.privateSubnetIds,
  chromaImage: config.chromaImage,
  chromaEfsId: dataServices.chromaEfs.id,
  chromaMountTargets: dataServices.chromaMountTargets,
  chromaDiscoveryServiceArn: discovery.chromaDiscoveryService.arn,
  chromaInternalHost: discovery.chromaInternalHost,
  providerParameterArns: parameterStore.providerParameterArns,
  mediaBucket: artifacts.mediaBucket,
});

export const ecsClusterName = ecsBase.cluster.name;
export const ec2CapacityProviderName = ecsBase.capacityProvider.name;
export const ecsAutoScalingGroupName = ecsBase.ecsAsg.name;
export const ecsNodeSecurityGroupId = securityGroups.ecsNodeSg.id;
export const appTasksSecurityGroupId = securityGroups.appTasksSg.id;
export const vpcId = networking.vpc.id;
export const publicSubnetIdsOutput = pulumi.output(networking.publicSubnetIds);
export const privateSubnetIdsOutput = pulumi.output(networking.privateSubnetIds);
// Used for one-off ECS tasks like migrations; must be private subnets (NAT-enabled).
export const subnetIds = pulumi.output(networking.privateSubnetIds);
export const allSubnetIdsOutput = pulumi.output(networking.allSubnetIds);
export const appAlbDnsName = routing.alb.dnsName;
export const appBaseUrl = routing.appBaseUrl;
export const coreBaseUrl = routing.coreBaseUrl;
export const djangoEcrRepositoryUrl = artifacts.djangoRepo.repositoryUrl;
export const streamingEcrRepositoryUrl = artifacts.streamingRepo.repositoryUrl;
export const staticBucketName = artifacts.staticBucket.bucket;
export const mediaBucketName = artifacts.mediaBucket.bucket;
export const logGroupName = artifacts.appLogs.name;
export const postgresAddress = dataServices.postgres.address;
export const redisPrimaryEndpoint = dataServices.redis.primaryEndpointAddress;
export const djangoServiceName = services.djangoService.name;
export const fastapiServiceName = services.fastapiService.name;
export const celeryWorkerServiceName = services.celeryWorkerService.name;
export const celeryBeatServiceName = services.celeryBeatService.name;
export const chromaServiceName = services.chromaService.name;
export const djangoMigrateTaskDefinitionArn = services.djangoMigrateTaskDefinition.arn;

import * as aws from "@pulumi/aws";
import { Tags } from "./config";

export function createDataServices(args: {
  namePrefix: string;
  tags: Tags;
  dbName: string;
  dbUsername: string;
  dbPassword: any;
  privateSubnetIds: any[];
  databaseSecurityGroupId: any;
  redisSecurityGroupId: any;
  efsSecurityGroupId: any;
}) {
  const dbSubnetGroup = new aws.rds.SubnetGroup("db-subnet-group", {
    name: `${args.namePrefix}-db-subnets`,
    subnetIds: args.privateSubnetIds,
    tags: args.tags,
  });

  const redisSubnetGroup = new aws.elasticache.SubnetGroup("redis-subnet-group", {
    name: `${args.namePrefix}-redis-subnets`,
    subnetIds: args.privateSubnetIds,
  });

  const postgres = new aws.rds.Instance("postgres", {
    identifier: `${args.namePrefix}-postgres`,
    allocatedStorage: 20,
    engine: "postgres",
    engineVersion: "15.7",
    instanceClass: "db.t4g.medium",
    dbName: args.dbName,
    username: args.dbUsername,
    password: args.dbPassword,
    dbSubnetGroupName: dbSubnetGroup.name,
    vpcSecurityGroupIds: [args.databaseSecurityGroupId],
    skipFinalSnapshot: true,
    publiclyAccessible: false,
    storageEncrypted: true,
    deletionProtection: false,
    tags: args.tags,
  });

  const redis = new aws.elasticache.ReplicationGroup("redis", {
    replicationGroupId: `${args.namePrefix}-redis`,
    description: `Redis for ${args.namePrefix}`,
    engine: "redis",
    engineVersion: "7.1",
    nodeType: "cache.t3.micro",
    numCacheClusters: 1,
    port: 6379,
    parameterGroupName: "default.redis7",
    automaticFailoverEnabled: false,
    subnetGroupName: redisSubnetGroup.name,
    securityGroupIds: [args.redisSecurityGroupId],
    tags: args.tags,
  });

  const chromaEfs = new aws.efs.FileSystem("chroma-efs", {
    creationToken: `${args.namePrefix}-chroma`,
    encrypted: true,
    tags: { ...args.tags, Name: `${args.namePrefix}-chroma-efs` },
  });

  const chromaMountTargets = args.privateSubnetIds.map((subnetId, index) => new aws.efs.MountTarget(`chroma-efs-mount-target-${index + 1}`, {
    fileSystemId: chromaEfs.id,
    subnetId,
    securityGroups: [args.efsSecurityGroupId],
  }));

  return { postgres, redis, chromaEfs, chromaMountTargets };
}

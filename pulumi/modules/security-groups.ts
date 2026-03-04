import * as aws from "@pulumi/aws";
import { Tags } from "./config";

export function createSecurityGroups(namePrefix: string, vpcId: aws.ec2.Vpc["id"], tags: Tags) {
  const ecsNodeSg = new aws.ec2.SecurityGroup("ecs-node-sg", {
    name: `${namePrefix}-ecs-node-sg`,
    description: "Security group for ECS EC2 container instances",
    vpcId,
    egress: [{ protocol: "-1", fromPort: 0, toPort: 0, cidrBlocks: ["0.0.0.0/0"] }],
    tags,
  });

  const albSg = new aws.ec2.SecurityGroup("alb-sg", {
    name: `${namePrefix}-alb-sg`,
    description: "Public ALB security group",
    vpcId,
    ingress: [
      { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"], description: "Public HTTP ingress" },
      { protocol: "tcp", fromPort: 443, toPort: 443, cidrBlocks: ["0.0.0.0/0"], description: "Public HTTPS ingress" },
    ],
    egress: [{ protocol: "-1", fromPort: 0, toPort: 0, cidrBlocks: ["0.0.0.0/0"] }],
    tags,
  });

  const appTasksSg = new aws.ec2.SecurityGroup("app-tasks-sg", {
    name: `${namePrefix}-app-tasks-sg`,
    description: "Security group for ECS app tasks",
    vpcId,
    ingress: [
      { protocol: "tcp", fromPort: 8000, toPort: 8001, securityGroups: [albSg.id], description: "ALB traffic to app" },
      { protocol: "tcp", fromPort: 8000, toPort: 8000, self: true, description: "Internal app traffic to Chroma" },
    ],
    egress: [{ protocol: "-1", fromPort: 0, toPort: 0, cidrBlocks: ["0.0.0.0/0"] }],
    tags,
  });

  const databaseSg = new aws.ec2.SecurityGroup("database-sg", {
    name: `${namePrefix}-database-sg`,
    description: "Security group for RDS PostgreSQL",
    vpcId,
    ingress: [{ protocol: "tcp", fromPort: 5432, toPort: 5432, securityGroups: [appTasksSg.id] }],
    egress: [{ protocol: "-1", fromPort: 0, toPort: 0, cidrBlocks: ["0.0.0.0/0"] }],
    tags,
  });

  const redisSg = new aws.ec2.SecurityGroup("redis-sg", {
    name: `${namePrefix}-redis-sg`,
    description: "Security group for ElastiCache Redis",
    vpcId,
    ingress: [{ protocol: "tcp", fromPort: 6379, toPort: 6379, securityGroups: [appTasksSg.id] }],
    egress: [{ protocol: "-1", fromPort: 0, toPort: 0, cidrBlocks: ["0.0.0.0/0"] }],
    tags,
  });

  const efsSg = new aws.ec2.SecurityGroup("efs-sg", {
    name: `${namePrefix}-efs-sg`,
    description: "Security group for Chroma EFS storage",
    vpcId,
    ingress: [{ protocol: "tcp", fromPort: 2049, toPort: 2049, securityGroups: [appTasksSg.id] }],
    egress: [{ protocol: "-1", fromPort: 0, toPort: 0, cidrBlocks: ["0.0.0.0/0"] }],
    tags,
  });

  return { ecsNodeSg, albSg, appTasksSg, databaseSg, redisSg, efsSg };
}

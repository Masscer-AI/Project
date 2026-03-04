import * as aws from "@pulumi/aws";
import { Tags } from "./config";

export function createEcsBase(args: {
  namePrefix: string;
  tags: Tags;
  instanceType: string;
  asgMinSize: number;
  asgDesiredSize: number;
  asgMaxSize: number;
  publicSubnetIds: any[];
  ecsNodeSecurityGroupId: any;
}) {
  const cluster = new aws.ecs.Cluster("masscer-cluster", {
    name: `${args.namePrefix}-cluster`,
    settings: [{ name: "containerInsights", value: "enabled" }],
    tags: args.tags,
  });

  const ecsInstanceRole = new aws.iam.Role("ecs-instance-role", {
    name: `${args.namePrefix}-ecs-instance-role`,
    assumeRolePolicy: aws.iam.assumeRolePolicyForPrincipal({ Service: "ec2.amazonaws.com" }),
    tags: args.tags,
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
    name: `${args.namePrefix}-ecs-instance-profile`,
    role: ecsInstanceRole.name,
    tags: args.tags,
  });

  const ecsAmiId = aws.ssm.getParameterOutput({
    name: "/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id",
  });

  const launchTemplate = new aws.ec2.LaunchTemplate("ecs-launch-template", {
    namePrefix: `${args.namePrefix}-ecs-`,
    imageId: ecsAmiId.value,
    instanceType: args.instanceType,
    iamInstanceProfile: { arn: ecsInstanceProfile.arn },
    vpcSecurityGroupIds: [args.ecsNodeSecurityGroupId],
    userData: cluster.name.apply((clusterName) => Buffer.from(`#!/bin/bash\necho ECS_CLUSTER=${clusterName} >> /etc/ecs/ecs.config\n`).toString("base64")),
    monitoring: { enabled: true },
    tagSpecifications: [{
      resourceType: "instance",
      tags: { ...args.tags, Name: `${args.namePrefix}-ecs-node` },
    }],
    tags: args.tags,
  });

  const ecsAsg = new aws.autoscaling.Group("ecs-asg", {
    name: `${args.namePrefix}-ecs-asg`,
    desiredCapacity: args.asgDesiredSize,
    minSize: args.asgMinSize,
    maxSize: args.asgMaxSize,
    vpcZoneIdentifiers: args.publicSubnetIds,
    healthCheckType: "EC2",
    launchTemplate: { id: launchTemplate.id, version: "$Latest" },
    tags: [
      { key: "Name", value: `${args.namePrefix}-ecs-node`, propagateAtLaunch: true },
      { key: "Project", value: args.tags.Project, propagateAtLaunch: true },
      { key: "Environment", value: args.tags.Environment, propagateAtLaunch: true },
      { key: "ManagedBy", value: args.tags.ManagedBy, propagateAtLaunch: true },
    ],
  });

  const capacityProvider = new aws.ecs.CapacityProvider("ecs-ec2-capacity-provider", {
    name: `${args.namePrefix}-ec2-cp`,
    autoScalingGroupProvider: {
      autoScalingGroupArn: ecsAsg.arn,
      managedTerminationProtection: "DISABLED",
      managedScaling: { status: "ENABLED", targetCapacity: 80, minimumScalingStepSize: 1, maximumScalingStepSize: 2 },
    },
    tags: args.tags,
  });

  const clusterCapacityProviders = new aws.ecs.ClusterCapacityProviders("cluster-capacity-providers", {
    clusterName: cluster.name,
    capacityProviders: [capacityProvider.name],
    defaultCapacityProviderStrategies: [{ capacityProvider: capacityProvider.name, weight: 1, base: 1 }],
  });

  const taskExecutionRole = new aws.iam.Role("ecs-task-execution-role", {
    name: `${args.namePrefix}-ecs-task-exec-role`,
    assumeRolePolicy: aws.iam.assumeRolePolicyForPrincipal({ Service: "ecs-tasks.amazonaws.com" }),
    tags: args.tags,
  });
  new aws.iam.RolePolicyAttachment("ecs-task-exec-policy", {
    role: taskExecutionRole.name,
    policyArn: "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
  });

  const taskRole = new aws.iam.Role("ecs-task-role", {
    name: `${args.namePrefix}-ecs-task-role`,
    assumeRolePolicy: aws.iam.assumeRolePolicyForPrincipal({ Service: "ecs-tasks.amazonaws.com" }),
    tags: args.tags,
  });

  return { cluster, ecsAsg, capacityProvider, clusterCapacityProviders, taskExecutionRole, taskRole };
}

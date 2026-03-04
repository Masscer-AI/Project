import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { Tags } from "./config";

export interface NetworkingResources {
  vpc: aws.ec2.Vpc;
  publicSubnetIds: pulumi.Output<string>[];
  privateSubnetIds: pulumi.Output<string>[];
  allSubnetIds: pulumi.Output<string>[];
}

export function createNetworking(namePrefix: string, tags: Tags, vpcCidr: string): NetworkingResources {
  const vpc = new aws.ec2.Vpc("vpc", {
    cidrBlock: vpcCidr,
    enableDnsHostnames: true,
    enableDnsSupport: true,
    tags: {
      ...tags,
      Name: `${namePrefix}-vpc`,
    },
  });

  const azs = aws.getAvailabilityZonesOutput({ state: "available" });
  const azA = azs.names.apply((names) => names[0]);
  const azB = azs.names.apply((names) => names[1]);

  const publicSubnetA = new aws.ec2.Subnet("public-subnet-a", {
    vpcId: vpc.id,
    cidrBlock: "10.42.0.0/20",
    availabilityZone: azA,
    mapPublicIpOnLaunch: true,
    tags: { ...tags, Name: `${namePrefix}-public-a`, Tier: "public" },
  });

  const publicSubnetB = new aws.ec2.Subnet("public-subnet-b", {
    vpcId: vpc.id,
    cidrBlock: "10.42.16.0/20",
    availabilityZone: azB,
    mapPublicIpOnLaunch: true,
    tags: { ...tags, Name: `${namePrefix}-public-b`, Tier: "public" },
  });

  const privateSubnetA = new aws.ec2.Subnet("private-subnet-a", {
    vpcId: vpc.id,
    cidrBlock: "10.42.128.0/20",
    availabilityZone: azA,
    mapPublicIpOnLaunch: false,
    tags: { ...tags, Name: `${namePrefix}-private-a`, Tier: "private" },
  });

  const privateSubnetB = new aws.ec2.Subnet("private-subnet-b", {
    vpcId: vpc.id,
    cidrBlock: "10.42.144.0/20",
    availabilityZone: azB,
    mapPublicIpOnLaunch: false,
    tags: { ...tags, Name: `${namePrefix}-private-b`, Tier: "private" },
  });

  const internetGateway = new aws.ec2.InternetGateway("internet-gateway", {
    vpcId: vpc.id,
    tags: { ...tags, Name: `${namePrefix}-igw` },
  });

  const publicRouteTable = new aws.ec2.RouteTable("public-route-table", {
    vpcId: vpc.id,
    routes: [{ cidrBlock: "0.0.0.0/0", gatewayId: internetGateway.id }],
    tags: { ...tags, Name: `${namePrefix}-public-rt` },
  });

  new aws.ec2.RouteTableAssociation("public-subnet-a-association", {
    subnetId: publicSubnetA.id,
    routeTableId: publicRouteTable.id,
  });
  new aws.ec2.RouteTableAssociation("public-subnet-b-association", {
    subnetId: publicSubnetB.id,
    routeTableId: publicRouteTable.id,
  });

  const privateRouteTable = new aws.ec2.RouteTable("private-route-table", {
    vpcId: vpc.id,
    tags: { ...tags, Name: `${namePrefix}-private-rt` },
  });

  new aws.ec2.RouteTableAssociation("private-subnet-a-association", {
    subnetId: privateSubnetA.id,
    routeTableId: privateRouteTable.id,
  });
  new aws.ec2.RouteTableAssociation("private-subnet-b-association", {
    subnetId: privateSubnetB.id,
    routeTableId: privateRouteTable.id,
  });

  const publicSubnetIds = [publicSubnetA.id, publicSubnetB.id];
  const privateSubnetIds = [privateSubnetA.id, privateSubnetB.id];

  return {
    vpc,
    publicSubnetIds,
    privateSubnetIds,
    allSubnetIds: [...publicSubnetIds, ...privateSubnetIds],
  };
}

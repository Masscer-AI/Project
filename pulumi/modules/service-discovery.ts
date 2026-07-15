import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { Tags } from "./config";

export function createChromaDiscovery(args: { namePrefix: string; tags: Tags; vpcId: any }) {
  const serviceDiscoveryNamespaceName = `${args.namePrefix}.internal`;
  const chromaInternalHost = pulumi.interpolate`chroma.${serviceDiscoveryNamespaceName}`;
  const fastapiInternalHost = pulumi.interpolate`fastapi.${serviceDiscoveryNamespaceName}`;

  const privateNamespace = new aws.servicediscovery.PrivateDnsNamespace("private-namespace", {
    name: serviceDiscoveryNamespaceName,
    vpc: args.vpcId,
    description: `Private namespace for ${args.namePrefix} ECS services`,
    tags: args.tags,
  });

  const chromaDiscoveryService = new aws.servicediscovery.Service("chroma-discovery-service", {
    name: "chroma",
    dnsConfig: {
      namespaceId: privateNamespace.id,
      dnsRecords: [{ ttl: 10, type: "A" }],
      routingPolicy: "MULTIVALUE",
    },
    healthCheckCustomConfig: { failureThreshold: 1 },
    tags: args.tags,
  });

  const fastapiDiscoveryService = new aws.servicediscovery.Service("fastapi-discovery-service", {
    name: "fastapi",
    dnsConfig: {
      namespaceId: privateNamespace.id,
      dnsRecords: [{ ttl: 10, type: "A" }],
      routingPolicy: "MULTIVALUE",
    },
    healthCheckCustomConfig: { failureThreshold: 1 },
    tags: args.tags,
  });

  return {
    chromaInternalHost,
    fastapiInternalHost,
    privateNamespace,
    chromaDiscoveryService,
    fastapiDiscoveryService,
  };
}

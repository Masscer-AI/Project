import * as aws from "@pulumi/aws";
import { Tags } from "./config";

export function createRouting(args: {
  namePrefix: string;
  tags: Tags;
  vpcId: any;
  albSecurityGroupId: any;
  publicSubnetIds: any[];
}) {
  const alb = new aws.lb.LoadBalancer("app-alb", {
    name: `${args.namePrefix}-alb`,
    internal: false,
    loadBalancerType: "application",
    securityGroups: [args.albSecurityGroupId],
    subnets: args.publicSubnetIds,
    tags: args.tags,
  });

  const djangoTargetGroup = new aws.lb.TargetGroup("django-tg", {
    name: `${args.namePrefix}-django`,
    port: 8000,
    protocol: "HTTP",
    targetType: "ip",
    vpcId: args.vpcId,
    healthCheck: { path: "/admin/login/", matcher: "200-399", interval: 30, timeout: 5, healthyThreshold: 2, unhealthyThreshold: 3 },
    tags: args.tags,
  });

  const fastapiTargetGroup = new aws.lb.TargetGroup("fastapi-tg", {
    name: `${args.namePrefix}-fastapi`,
    port: 8001,
    protocol: "HTTP",
    targetType: "ip",
    vpcId: args.vpcId,
    healthCheck: { path: "/", matcher: "200-399", interval: 30, timeout: 5, healthyThreshold: 2, unhealthyThreshold: 3 },
    tags: args.tags,
  });

  const httpListener = new aws.lb.Listener("http-listener", {
    loadBalancerArn: alb.arn,
    port: 80,
    protocol: "HTTP",
    defaultActions: [{ type: "forward", targetGroupArn: fastapiTargetGroup.arn }],
    tags: args.tags,
  });

  new aws.lb.ListenerRule("django-path-rules", {
    listenerArn: httpListener.arn,
    priority: 10,
    actions: [{ type: "forward", targetGroupArn: djangoTargetGroup.arn }],
    conditions: [{ pathPattern: { values: ["/v1/*", "/admin/*", "/static/*", "/media/*"] } }],
    tags: args.tags,
  });

  new aws.lb.ListenerRule("socketio-path-rule", {
    listenerArn: httpListener.arn,
    priority: 20,
    actions: [{ type: "forward", targetGroupArn: fastapiTargetGroup.arn }],
    conditions: [{ pathPattern: { values: ["/socket.io/*"] } }],
    tags: args.tags,
  });

  return { alb, djangoTargetGroup, fastapiTargetGroup, httpListener };
}

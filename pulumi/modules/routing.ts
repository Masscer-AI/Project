import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { Tags } from "./config";

export function createRouting(args: {
  namePrefix: string;
  tags: Tags;
  vpcId: any;
  albSecurityGroupId: any;
  publicSubnetIds: any[];
  rootDomain: string;
  appDomain: string;
  coreDomain: string;
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
    // ALB health checks can hit Django with host headers that may return 400.
    // Accept 400 for health checks to avoid constant task recycling/503 spikes.
    healthCheck: { path: "/admin/login/", matcher: "200-400", interval: 30, timeout: 5, healthyThreshold: 2, unhealthyThreshold: 3 },
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

  const customDomainsEnabled = Boolean(args.rootDomain && args.appDomain && args.coreDomain);
  const appBaseUrl = customDomainsEnabled
    ? pulumi.output(`https://${args.appDomain}`)
    : pulumi.interpolate`http://${alb.dnsName}`;
  const coreBaseUrl = customDomainsEnabled
    ? pulumi.output(`https://${args.coreDomain}`)
    : pulumi.interpolate`http://${alb.dnsName}`;

  let httpsListener: aws.lb.Listener | undefined;

  if (customDomainsEnabled) {
    const zone = aws.route53.getZoneOutput({
      name: args.rootDomain,
      privateZone: false,
    });

    const cert = new aws.acm.Certificate("app-cert", {
      domainName: `*.${args.rootDomain}`,
      validationMethod: "DNS",
      tags: args.tags,
    });

    const certValidationRecord = new aws.route53.Record("app-cert-validation", {
      zoneId: zone.zoneId,
      name: cert.domainValidationOptions.apply((options) => options[0].resourceRecordName),
      type: cert.domainValidationOptions.apply((options) => options[0].resourceRecordType),
      records: [cert.domainValidationOptions.apply((options) => options[0].resourceRecordValue)],
      ttl: 60,
    });

    const certValidation = new aws.acm.CertificateValidation("app-cert-validation-complete", {
      certificateArn: cert.arn,
      validationRecordFqdns: [certValidationRecord.fqdn],
    });

    httpsListener = new aws.lb.Listener("https-listener", {
      loadBalancerArn: alb.arn,
      port: 443,
      protocol: "HTTPS",
      sslPolicy: "ELBSecurityPolicy-TLS13-1-2-2021-06",
      certificateArn: certValidation.certificateArn,
      defaultActions: [{ type: "forward", targetGroupArn: fastapiTargetGroup.arn }],
      tags: args.tags,
    });

    const httpListener = new aws.lb.Listener("http-listener", {
      loadBalancerArn: alb.arn,
      port: 80,
      protocol: "HTTP",
      defaultActions: [{
        type: "redirect",
        redirect: {
          protocol: "HTTPS",
          port: "443",
          statusCode: "HTTP_301",
        },
      }],
      tags: args.tags,
    });

    new aws.lb.ListenerRule("core-host-rule", {
      listenerArn: httpsListener.arn,
      priority: 10,
      actions: [{ type: "forward", targetGroupArn: djangoTargetGroup.arn }],
      conditions: [{ hostHeader: { values: [args.coreDomain] } }],
      tags: args.tags,
    });

    new aws.lb.ListenerRule("app-django-path-rules", {
      listenerArn: httpsListener.arn,
      priority: 20,
      actions: [{ type: "forward", targetGroupArn: djangoTargetGroup.arn }],
      conditions: [
        { hostHeader: { values: [args.appDomain] } },
        { pathPattern: { values: ["/v1/*", "/static/*", "/media/*"] } },
      ],
      tags: args.tags,
    });

    new aws.lb.ListenerRule("app-socketio-path-rule", {
      listenerArn: httpsListener.arn,
      priority: 30,
      actions: [{ type: "forward", targetGroupArn: fastapiTargetGroup.arn }],
      conditions: [
        { hostHeader: { values: [args.appDomain] } },
        { pathPattern: { values: ["/socket.io/*"] } },
      ],
      tags: args.tags,
    });

    new aws.route53.Record("app-domain-alias-a", {
      zoneId: zone.zoneId,
      name: args.appDomain,
      type: "A",
      aliases: [{ name: alb.dnsName, zoneId: alb.zoneId, evaluateTargetHealth: true }],
    });

    new aws.route53.Record("core-domain-alias-a", {
      zoneId: zone.zoneId,
      name: args.coreDomain,
      type: "A",
      aliases: [{ name: alb.dnsName, zoneId: alb.zoneId, evaluateTargetHealth: true }],
    });

    return { alb, djangoTargetGroup, fastapiTargetGroup, httpListener, httpsListener, appBaseUrl, coreBaseUrl };
  }

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

  return { alb, djangoTargetGroup, fastapiTargetGroup, httpListener, httpsListener, appBaseUrl, coreBaseUrl };
}

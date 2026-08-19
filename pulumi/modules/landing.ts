import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { Tags } from "./config";

export type LandingSite = {
  bucket: aws.s3.BucketV2;
  distribution: aws.cloudfront.Distribution;
  landingUrl: pulumi.Output<string>;
};

export function createLandingSite(args: {
  namePrefix: string;
  tags: Tags;
  rootDomain: string;
}): LandingSite | undefined {
  if (!args.rootDomain) {
    return undefined;
  }

  const zone = aws.route53.getZoneOutput({
    name: args.rootDomain,
    privateZone: false,
  });

  const bucket = new aws.s3.BucketV2("landing-bucket", {
    bucket: `${args.namePrefix}-landing`,
    tags: args.tags,
  });

  new aws.s3.BucketServerSideEncryptionConfigurationV2("landing-bucket-encryption", {
    bucket: bucket.id,
    rules: [{ applyServerSideEncryptionByDefault: { sseAlgorithm: "AES256" } }],
  });

  new aws.s3.BucketPublicAccessBlock("landing-bucket-public-access", {
    bucket: bucket.id,
    blockPublicAcls: true,
    blockPublicPolicy: true,
    ignorePublicAcls: true,
    restrictPublicBuckets: true,
  });

  new aws.s3.BucketOwnershipControls("landing-bucket-ownership", {
    bucket: bucket.id,
    rule: { objectOwnership: "BucketOwnerEnforced" },
  });

  const oac = new aws.cloudfront.OriginAccessControl("landing-oac", {
    name: `${args.namePrefix}-landing-oac`,
    description: "OAC for Masscer landing site",
    originAccessControlOriginType: "s3",
    signingBehavior: "always",
    signingProtocol: "sigv4",
  });

  const wwwDomain = `www.${args.rootDomain}`;
  const cert = new aws.acm.Certificate("landing-cert", {
    domainName: args.rootDomain,
    subjectAlternativeNames: [wwwDomain],
    validationMethod: "DNS",
    tags: args.tags,
  });

  const dvoFor = (domain: string) =>
    cert.domainValidationOptions.apply((options) => {
      const match = options.find((o) => o.domainName === domain) ?? options[0];
      return match;
    });

  const apexDvo = dvoFor(args.rootDomain);
  const wwwDvo = dvoFor(wwwDomain);

  const apexValidation = new aws.route53.Record("landing-cert-validation-apex", {
    zoneId: zone.zoneId,
    name: apexDvo.apply((o) => o.resourceRecordName),
    type: apexDvo.apply((o) => o.resourceRecordType),
    records: [apexDvo.apply((o) => o.resourceRecordValue)],
    ttl: 60,
    allowOverwrite: true,
  });

  const wwwValidation = new aws.route53.Record("landing-cert-validation-www", {
    zoneId: zone.zoneId,
    name: wwwDvo.apply((o) => o.resourceRecordName),
    type: wwwDvo.apply((o) => o.resourceRecordType),
    records: [wwwDvo.apply((o) => o.resourceRecordValue)],
    ttl: 60,
    allowOverwrite: true,
  });

  const certValidation = new aws.acm.CertificateValidation("landing-cert-validation-complete", {
    certificateArn: cert.arn,
    validationRecordFqdns: [apexValidation.fqdn, wwwValidation.fqdn],
  });

  const distribution = new aws.cloudfront.Distribution("landing-cdn", {
    enabled: true,
    isIpv6Enabled: true,
    comment: `${args.namePrefix} landing (${args.rootDomain})`,
    aliases: [args.rootDomain, wwwDomain],
    defaultRootObject: "index.html",
    priceClass: "PriceClass_100",
    httpVersion: "http2and3",
    origins: [{
      originId: "landing-s3",
      domainName: bucket.bucketRegionalDomainName,
      originAccessControlId: oac.id,
    }],
    defaultCacheBehavior: {
      targetOriginId: "landing-s3",
      viewerProtocolPolicy: "redirect-to-https",
      allowedMethods: ["GET", "HEAD", "OPTIONS"],
      cachedMethods: ["GET", "HEAD"],
      compress: true,
      forwardedValues: {
        queryString: false,
        cookies: { forward: "none" },
      },
      minTtl: 0,
      defaultTtl: 3600,
      maxTtl: 86400,
    },
    customErrorResponses: [
      { errorCode: 403, responseCode: 200, responsePagePath: "/index.html", errorCachingMinTtl: 0 },
      { errorCode: 404, responseCode: 200, responsePagePath: "/index.html", errorCachingMinTtl: 0 },
    ],
    restrictions: {
      geoRestriction: { restrictionType: "none" },
    },
    viewerCertificate: {
      acmCertificateArn: certValidation.certificateArn,
      sslSupportMethod: "sni-only",
      minimumProtocolVersion: "TLSv1.2_2021",
    },
    tags: args.tags,
  });

  new aws.s3.BucketPolicy("landing-bucket-policy", {
    bucket: bucket.id,
    policy: pulumi.all([bucket.arn, distribution.arn]).apply(([bucketArn, distributionArn]) =>
      JSON.stringify({
        Version: "2012-10-17",
        Statement: [{
          Sid: "AllowCloudFrontServicePrincipalRead",
          Effect: "Allow",
          Principal: { Service: "cloudfront.amazonaws.com" },
          Action: "s3:GetObject",
          Resource: `${bucketArn}/*`,
          Condition: {
            StringEquals: { "AWS:SourceArn": distributionArn },
          },
        }],
      })),
  });

  new aws.route53.Record("landing-apex-a", {
    zoneId: zone.zoneId,
    name: args.rootDomain,
    type: "A",
    aliases: [{
      name: distribution.domainName,
      zoneId: distribution.hostedZoneId,
      evaluateTargetHealth: false,
    }],
  });

  new aws.route53.Record("landing-apex-aaaa", {
    zoneId: zone.zoneId,
    name: args.rootDomain,
    type: "AAAA",
    aliases: [{
      name: distribution.domainName,
      zoneId: distribution.hostedZoneId,
      evaluateTargetHealth: false,
    }],
  });

  new aws.route53.Record("landing-www-a", {
    zoneId: zone.zoneId,
    name: wwwDomain,
    type: "A",
    aliases: [{
      name: distribution.domainName,
      zoneId: distribution.hostedZoneId,
      evaluateTargetHealth: false,
    }],
  });

  new aws.route53.Record("landing-www-aaaa", {
    zoneId: zone.zoneId,
    name: wwwDomain,
    type: "AAAA",
    aliases: [{
      name: distribution.domainName,
      zoneId: distribution.hostedZoneId,
      evaluateTargetHealth: false,
    }],
  });

  return {
    bucket,
    distribution,
    landingUrl: pulumi.output(`https://${args.rootDomain}`),
  };
}

import * as aws from "@pulumi/aws";
import { Tags } from "./config";

function secureBucket(resourceName: string, bucketName: string, tags: Tags) {
  const bucket = new aws.s3.BucketV2(resourceName, { bucket: bucketName, tags });

  new aws.s3.BucketServerSideEncryptionConfigurationV2(`${resourceName}-encryption`, {
    bucket: bucket.id,
    rules: [{ applyServerSideEncryptionByDefault: { sseAlgorithm: "AES256" } }],
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

function publicReadBucket(resourceName: string, bucketName: string, tags: Tags) {
  const bucket = new aws.s3.BucketV2(resourceName, { bucket: bucketName, tags });

  new aws.s3.BucketServerSideEncryptionConfigurationV2(`${resourceName}-encryption`, {
    bucket: bucket.id,
    rules: [{ applyServerSideEncryptionByDefault: { sseAlgorithm: "AES256" } }],
  });

  new aws.s3.BucketVersioningV2(`${resourceName}-versioning`, {
    bucket: bucket.id,
    versioningConfiguration: { status: "Enabled" },
  });

  // Allow public reads via bucket policy; block ACL-based public access only.
  const publicAccessBlock = new aws.s3.BucketPublicAccessBlock(`${resourceName}-public-access`, {
    bucket: bucket.id,
    blockPublicAcls: true,
    blockPublicPolicy: false,
    ignorePublicAcls: true,
    restrictPublicBuckets: false,
  });

  new aws.s3.BucketPolicy(`${resourceName}-policy`, {
    bucket: bucket.id,
    policy: bucket.arn.apply((arn) => JSON.stringify({
      Version: "2012-10-17",
      Statement: [{
        Sid: "PublicReadGetObject",
        Effect: "Allow",
        Principal: "*",
        Action: "s3:GetObject",
        Resource: `${arn}/*`,
      }],
    })),
  }, { dependsOn: [publicAccessBlock] });

  return bucket;
}

export function createArtifacts(namePrefix: string, tags: Tags) {
  const staticBucket = secureBucket("static-assets-bucket", `${namePrefix}-static-assets`, tags);
  const mediaBucket = publicReadBucket("media-assets-bucket", `${namePrefix}-media-assets`, tags);

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
    rules: [{
      rulePriority: 1,
      description: "Keep last 15 images",
      selection: { tagStatus: "any", countType: "imageCountMoreThan", countNumber: 15 },
      action: { type: "expire" },
    }],
  });

  new aws.ecr.LifecyclePolicy("django-repo-policy", { repository: djangoRepo.name, policy: lifecyclePolicy });
  new aws.ecr.LifecyclePolicy("streaming-repo-policy", { repository: streamingRepo.name, policy: lifecyclePolicy });

  const appLogs = new aws.cloudwatch.LogGroup("application-logs", {
    name: `/ecs/${namePrefix}`,
    retentionInDays: 30,
    tags,
  });

  return { staticBucket, mediaBucket, djangoRepo, streamingRepo, appLogs };
}

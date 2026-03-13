import * as pulumi from "@pulumi/pulumi";

export type Tags = Record<string, string>;

export interface AppConfig {
  environment: string;
  namePrefix: string;
  tags: Tags;
  vpcCidr: string;
  instanceType: string;
  asgMinSize: number;
  asgDesiredSize: number;
  asgMaxSize: number;
  djangoDesiredCount: number;
  fastapiDesiredCount: number;
  celeryWorkerDesiredCount: number;
  celeryBeatDesiredCount: number;
  chromaDesiredCount: number;
  dbName: string;
  dbUsername: string;
  dbPassword: pulumi.Output<string>;
  djangoSecretKey: pulumi.Output<string>;
  djangoImageTag: string;
  streamingImageTag: string;
  chromaImage: string;
  corsOrigins: string;
  allowedExtraHosts: string;
  rootDomain: string;
  appDomain: string;
  coreDomain: string;
  openAiApiKey: pulumi.Output<string>;
  anthropicApiKey: pulumi.Output<string>;
  xaiApiKey: pulumi.Output<string>;
  pexelsApiKey: pulumi.Output<string>;
  braveApiKey: pulumi.Output<string>;
  bflApiKey: pulumi.Output<string>;
  runwayApiKey: pulumi.Output<string>;
  whatsappGraphApiToken: pulumi.Output<string>;
  whatsappWebhookVerifyToken: pulumi.Output<string>;
}

export function loadConfig(): AppConfig {
  const cfg = new pulumi.Config();
  const environment = cfg.get("environment") ?? pulumi.getStack();
  const namePrefix = cfg.get("namePrefix") ?? `masscer-${environment}`;

  return {
    environment,
    namePrefix,
    tags: {
      Project: "masscer",
      Environment: environment,
      ManagedBy: "pulumi",
    },
    vpcCidr: cfg.get("vpcCidr") ?? "10.42.0.0/16",
    instanceType: cfg.get("instanceType") ?? "t3.medium",
    asgMinSize: cfg.getNumber("asgMinSize") ?? 1,
    asgDesiredSize: cfg.getNumber("asgDesiredSize") ?? 1,
    asgMaxSize: cfg.getNumber("asgMaxSize") ?? 2,
    djangoDesiredCount: cfg.getNumber("djangoDesiredCount") ?? 1,
    fastapiDesiredCount: cfg.getNumber("fastapiDesiredCount") ?? 1,
    celeryWorkerDesiredCount: cfg.getNumber("celeryWorkerDesiredCount") ?? 1,
    celeryBeatDesiredCount: cfg.getNumber("celeryBeatDesiredCount") ?? 1,
    chromaDesiredCount: cfg.getNumber("chromaDesiredCount") ?? 1,
    dbName: cfg.get("dbName") ?? "masscer",
    dbUsername: cfg.get("dbUsername") ?? "masscer",
    dbPassword: cfg.requireSecret("dbPassword"),
    djangoSecretKey: cfg.requireSecret("djangoSecretKey"),
    djangoImageTag: cfg.get("djangoImageTag") ?? "latest",
    streamingImageTag: cfg.get("streamingImageTag") ?? "latest",
    chromaImage: cfg.get("chromaImage") ?? "chromadb/chroma:0.5.11",
    corsOrigins: cfg.get("corsOrigins") ?? "*",
    allowedExtraHosts: cfg.get("allowedExtraHosts") ?? "",
    rootDomain: cfg.get("rootDomain") ?? "",
    appDomain: cfg.get("appDomain") ?? "",
    coreDomain: cfg.get("coreDomain") ?? "",
    openAiApiKey: cfg.getSecret("openAiApiKey") ?? pulumi.output(""),
    anthropicApiKey: cfg.getSecret("anthropicApiKey") ?? pulumi.output(""),
    xaiApiKey: cfg.getSecret("xaiApiKey") ?? pulumi.output(""),
    pexelsApiKey: cfg.getSecret("pexelsApiKey") ?? pulumi.output(""),
    braveApiKey: cfg.getSecret("braveApiKey") ?? pulumi.output(""),
    bflApiKey: cfg.getSecret("bflApiKey") ?? pulumi.output(""),
    runwayApiKey: cfg.getSecret("runwayApiKey") ?? pulumi.output(""),
    whatsappGraphApiToken: cfg.getSecret("whatsappGraphApiToken") ?? pulumi.output(""),
    whatsappWebhookVerifyToken: cfg.getSecret("whatsappWebhookVerifyToken") ?? pulumi.output(""),
  };
}

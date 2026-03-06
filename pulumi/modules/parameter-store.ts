import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

export interface ProviderParameterArns {
  openAiApiKeyArn: pulumi.Output<string>;
  anthropicApiKeyArn: pulumi.Output<string>;
  xaiApiKeyArn: pulumi.Output<string>;
  pexelsApiKeyArn: pulumi.Output<string>;
  braveApiKeyArn: pulumi.Output<string>;
  bflApiKeyArn: pulumi.Output<string>;
  runwayApiKeyArn: pulumi.Output<string>;
  whatsappGraphApiTokenArn: pulumi.Output<string>;
  whatsappWebhookVerifyTokenArn: pulumi.Output<string>;
}

export function createProviderParameters(args: {
  namePrefix: string;
  openAiApiKey: pulumi.Output<string>;
  anthropicApiKey: pulumi.Output<string>;
  xaiApiKey: pulumi.Output<string>;
  pexelsApiKey: pulumi.Output<string>;
  braveApiKey: pulumi.Output<string>;
  bflApiKey: pulumi.Output<string>;
  runwayApiKey: pulumi.Output<string>;
  whatsappGraphApiToken: pulumi.Output<string>;
  whatsappWebhookVerifyToken: pulumi.Output<string>;
  taskExecutionRoleName: pulumi.Input<string>;
}) {
  const basePath = `/${args.namePrefix}/providers`;

  const openAiApiKey = new aws.ssm.Parameter("openai-api-key-param", {
    name: `${basePath}/OPENAI_API_KEY`,
    type: "SecureString",
    value: args.openAiApiKey,
  });

  const anthropicApiKey = new aws.ssm.Parameter("anthropic-api-key-param", {
    name: `${basePath}/ANTHROPIC_API_KEY`,
    type: "SecureString",
    value: args.anthropicApiKey,
  });

  const xaiApiKey = new aws.ssm.Parameter("xai-api-key-param", {
    name: `${basePath}/XAI_API_KEY`,
    type: "SecureString",
    value: args.xaiApiKey,
  });

  const pexelsApiKey = new aws.ssm.Parameter("pexels-api-key-param", {
    name: `${basePath}/PEXELS_API_KEY`,
    type: "SecureString",
    value: args.pexelsApiKey,
  });

  const braveApiKey = new aws.ssm.Parameter("brave-api-key-param", {
    name: `${basePath}/BRAVE_API_KEY`,
    type: "SecureString",
    value: args.braveApiKey,
  });

  const bflApiKey = new aws.ssm.Parameter("bfl-api-key-param", {
    name: `${basePath}/BFL_API_KEY`,
    type: "SecureString",
    value: args.bflApiKey,
  });

  const runwayApiKey = new aws.ssm.Parameter("runway-api-key-param", {
    name: `${basePath}/RUNWAY_API_KEY`,
    type: "SecureString",
    value: args.runwayApiKey,
  });

  const whatsappGraphApiToken = new aws.ssm.Parameter("whatsapp-graph-api-token-param", {
    name: `${basePath}/WHATSAPP_GRAPH_API_TOKEN`,
    type: "SecureString",
    value: args.whatsappGraphApiToken,
  });

  const whatsappWebhookVerifyToken = new aws.ssm.Parameter("whatsapp-webhook-verify-token-param", {
    name: `${basePath}/WHATSAPP_WEBHOOK_VERIFY_TOKEN`,
    type: "SecureString",
    value: args.whatsappWebhookVerifyToken,
  });

  const parameterArns = [
    openAiApiKey.arn,
    anthropicApiKey.arn,
    xaiApiKey.arn,
    pexelsApiKey.arn,
    braveApiKey.arn,
    bflApiKey.arn,
    runwayApiKey.arn,
    whatsappGraphApiToken.arn,
    whatsappWebhookVerifyToken.arn,
  ];

  new aws.iam.RolePolicy("ecs-task-exec-ssm-policy", {
    role: args.taskExecutionRoleName,
    policy: pulumi.all(parameterArns).apply((arns) => JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Action: ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
          Resource: arns,
        },
        {
          Effect: "Allow",
          Action: ["kms:Decrypt"],
          Resource: "*",
        },
      ],
    })),
  });

  const providerParameterArns: ProviderParameterArns = {
    openAiApiKeyArn: openAiApiKey.arn,
    anthropicApiKeyArn: anthropicApiKey.arn,
    xaiApiKeyArn: xaiApiKey.arn,
    pexelsApiKeyArn: pexelsApiKey.arn,
    braveApiKeyArn: braveApiKey.arn,
    bflApiKeyArn: bflApiKey.arn,
    runwayApiKeyArn: runwayApiKey.arn,
    whatsappGraphApiTokenArn: whatsappGraphApiToken.arn,
    whatsappWebhookVerifyTokenArn: whatsappWebhookVerifyToken.arn,
  };

  return { providerParameterArns };
}

import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

export interface ProviderParameterArns {
  openAiApiKeyArn: pulumi.Output<string>;
  anthropicApiKeyArn: pulumi.Output<string>;
  xaiApiKeyArn: pulumi.Output<string>;
  pexelsApiKeyArn: pulumi.Output<string>;
  firecrawlApiKeyArn: pulumi.Output<string>;
  bflApiKeyArn: pulumi.Output<string>;
  runwayApiKeyArn: pulumi.Output<string>;
  resendApiKeyArn: pulumi.Output<string>;
  whatsappGraphApiTokenArn: pulumi.Output<string>;
  whatsappWebhookVerifyTokenArn: pulumi.Output<string>;
}

export function createProviderParameters(args: {
  namePrefix: string;
  openAiApiKey: pulumi.Input<string>;
  anthropicApiKey: pulumi.Input<string>;
  xaiApiKey: pulumi.Input<string>;
  pexelsApiKey: pulumi.Input<string>;
  firecrawlApiKey: pulumi.Input<string>;
  bflApiKey: pulumi.Input<string>;
  runwayApiKey: pulumi.Input<string>;
  whatsappGraphApiToken: pulumi.Input<string>;
  whatsappWebhookVerifyToken: pulumi.Input<string>;
  googleOauthClientId: pulumi.Input<string>;
  taskExecutionRoleName: pulumi.Input<string>;
}) {
  const basePath = `/${args.namePrefix}/providers`;
  const normalizeSecret = (value: pulumi.Input<string>) =>
    pulumi.output(value).apply((v) => {
      const trimmed = (v ?? "").trim();
      // SSM SecureString does not allow empty values.
      return trimmed.length > 0 ? trimmed : "__UNSET__";
    });

  const openAiApiKey = new aws.ssm.Parameter("openai-api-key-param", {
    name: `${basePath}/OPENAI_API_KEY`,
    type: "SecureString",
    value: normalizeSecret(args.openAiApiKey),
  });

  const anthropicApiKey = new aws.ssm.Parameter("anthropic-api-key-param", {
    name: `${basePath}/ANTHROPIC_API_KEY`,
    type: "SecureString",
    value: normalizeSecret(args.anthropicApiKey),
  });

  const xaiApiKey = new aws.ssm.Parameter("xai-api-key-param", {
    name: `${basePath}/XAI_API_KEY`,
    type: "SecureString",
    value: normalizeSecret(args.xaiApiKey),
  });

  const pexelsApiKey = new aws.ssm.Parameter("pexels-api-key-param", {
    name: `${basePath}/PEXELS_API_KEY`,
    type: "SecureString",
    value: normalizeSecret(args.pexelsApiKey),
  });

  const firecrawlApiKey = new aws.ssm.Parameter("firecrawl-api-key-param", {
    name: `${basePath}/FIRECRAWL_API_KEY`,
    type: "SecureString",
    value: normalizeSecret(args.firecrawlApiKey),
  });

  const bflApiKey = new aws.ssm.Parameter("bfl-api-key-param", {
    name: `${basePath}/BFL_API_KEY`,
    type: "SecureString",
    value: normalizeSecret(args.bflApiKey),
  });

  const runwayApiKey = new aws.ssm.Parameter("runway-api-key-param", {
    name: `${basePath}/RUNWAY_API_KEY`,
    type: "SecureString",
    value: normalizeSecret(args.runwayApiKey),
  });

  const resendApiKey = new aws.ssm.Parameter("resend-api-key-param", {
    name: `${basePath}/RESEND_API_KEY`,
    type: "SecureString",
    value: "__UNSET__",
  }, {
    ignoreChanges: ["value"],
  });

  const whatsappGraphApiToken = new aws.ssm.Parameter("whatsapp-graph-api-token-param", {
    name: `${basePath}/WHATSAPP_GRAPH_API_TOKEN`,
    type: "SecureString",
    value: normalizeSecret(args.whatsappGraphApiToken),
  });

  const whatsappWebhookVerifyToken = new aws.ssm.Parameter("whatsapp-webhook-verify-token-param", {
    name: `${basePath}/WHATSAPP_WEBHOOK_VERIFY_TOKEN`,
    type: "SecureString",
    value: normalizeSecret(args.whatsappWebhookVerifyToken),
  });

  const googleOauthClientId = new aws.ssm.Parameter("google-oauth-client-id-param", {
    name: `${basePath}/GOOGLE_OAUTH_CLIENT_ID`,
    type: "String",
    value: normalizeSecret(args.googleOauthClientId),
  });

  const parameterArns = [
    openAiApiKey.arn,
    anthropicApiKey.arn,
    xaiApiKey.arn,
    pexelsApiKey.arn,
    firecrawlApiKey.arn,
    bflApiKey.arn,
    runwayApiKey.arn,
    resendApiKey.arn,
    whatsappGraphApiToken.arn,
    whatsappWebhookVerifyToken.arn,
    googleOauthClientId.arn,
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
    firecrawlApiKeyArn: firecrawlApiKey.arn,
    bflApiKeyArn: bflApiKey.arn,
    runwayApiKeyArn: runwayApiKey.arn,
    resendApiKeyArn: resendApiKey.arn,
    whatsappGraphApiTokenArn: whatsappGraphApiToken.arn,
    whatsappWebhookVerifyTokenArn: whatsappWebhookVerifyToken.arn,
  };

  return { providerParameterArns };
}

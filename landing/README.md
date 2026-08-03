# Masscer marketing site

Public site for [https://masscer.ai](https://masscer.ai) (Google OAuth consent home page + privacy/terms).

Localized in **English** and **Spanish**. Language is detected from the browser
(`navigator.language`), persisted in `localStorage` (`language`), and can be
overridden with the EN/ES control in the header/footer.

## Local

```bash
npm install
npm run dev
```

## Deploy

Infrastructure (S3 + CloudFront + ACM + Route53) lives in `../pulumi/modules/landing.ts`.

```bash
cd ../pulumi
pulumi up          # once, to create/update CDN + DNS
./deploy-landing.sh
```

## Google OAuth consent URLs

- Application home page: `https://masscer.ai`
- Privacy policy: `https://masscer.ai/privacy`
- Authorized domain: `masscer.ai`

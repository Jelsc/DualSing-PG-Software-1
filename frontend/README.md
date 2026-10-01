# DualSign Frontend

The frontend has three explicit web surfaces:

| Route | Audience | Scope |
| --- | --- | --- |
| `/` | Everyone | Product surface index linking to the portal and internal shell |
| `/portal` | Company members | Session and CSRF protected, institution-scoped vocabulary and pilot-cohort workbench |
| `/backoffice` | DualSign staff | Internal operations shell with honest placeholders for future platform tooling |

Flutter remains the consumer/mobile client for Free, Plus, and enterprise-provisioned access. The portal displays effective billing status and institution administrators can open hosted Stripe Checkout for Enterprise. Backoffice billing is read-only. Access origin is represented by the backend, with no SSO or automatic email-domain validation. Use Stripe test-mode placeholders and mocked backend tests only; Google Play distribution later requires Play Billing migration.

Institution administrators create, activate, and close pilot cohorts in `/portal`, then manage active institution members in each participant roster. Roster data is limited to authorized institutional identifiers, enrollment lifecycle, consent state, and existing aggregate cohort reports; raw attempts are not shown. Flutter continues selecting assigned/enrolled cohorts and reporting through the server-backed mobile API. `/backoffice` remains for internal DualSign operations. The MVP is intentionally synthetic: no camera recognition, real avatar assets, real dataset, advanced analytics, or ML accuracy claim is bundled. Pilot reports are aggregate diagnostics.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

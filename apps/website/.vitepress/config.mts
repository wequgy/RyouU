import { defineConfig } from 'vitepress';

export default defineConfig({
  title: 'RyouU Suite',
  description: 'Layered, server-enforced identity verification & live interview integrity monitoring',
  head: [
    ['link', { rel: 'icon', type: 'image/png', href: '/favicon.png' }],
    ['link', { rel: 'preconnect', href: 'https://fonts.googleapis.com' }],
    ['link', { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' }],
    ['link', { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap' }],
    ['meta', { property: 'og:title', content: 'RyouU Suite — Server-Enforced Identity Verification' }],
    ['meta', { property: 'og:description', content: 'Know who is really on the other end, even when faces and voices can be cloned. Layered, server-enforced identity verification with human-in-the-loop review.' }],
    ['meta', { property: 'og:image', content: '/images/ryouu-suite-logo.png' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
  ],
  cleanUrls: true,
  themeConfig: {
    logo: {
      light: '/images/ryouu-navbar-light.png',
      dark: '/images/ryouu-navbar-dark.png',
      alt: 'RyouU Suite'
    },
    siteTitle: false,
    nav: [
      { text: 'Documentation', link: '/overview' },
      { text: 'Quickstart', link: '/quickstart' },
      { text: 'Reading Verdict', link: '/reading-the-verdict' },
      { text: 'API Reference', link: '/reference/api' },
      { text: 'Sandbox', link: '/reference/sandbox' },
    ],
    sidebar: [
      {
        text: 'Getting Started',
        collapsed: false,
        items: [
          { text: 'Overview & Architecture', link: '/overview' },
          { text: 'Quickstart (15 Min)', link: '/quickstart' },
          { text: 'Reading the Verdict', link: '/reading-the-verdict' },
          { text: 'Merge into Your Product', link: '/integration-checklist' },
        ],
      },
      {
        text: 'Core Concepts',
        collapsed: false,
        items: [
          { text: 'Check Contract & Results', link: '/concepts/check-contract' },
          { text: 'Policies & Gates', link: '/concepts/policies' },
          { text: 'Human in the Loop', link: '/concepts/human-review' },
          { text: 'Evidence & Retention', link: '/concepts/evidence-retention' },
        ],
      },
      {
        text: 'SDKs & Integrations',
        collapsed: false,
        items: [
          { text: 'Python SDK', link: '/sdks/python' },
          { text: 'Node.js / TypeScript SDK', link: '/sdks/node' },
          { text: 'React Native SDK', link: '/sdks/react-native' },
          { text: 'Android SDK', link: '/sdks/android' },
          { text: 'Webhooks & Signing', link: '/sdks/webhooks' },
          { text: 'Idempotency & Errors', link: '/sdks/idempotency' },
        ],
      },
      {
        text: 'Live Interview Overlay',
        collapsed: false,
        items: [
          { text: 'Installation & Launch', link: '/overlay/installation' },
          { text: 'Interviewer Token Minting', link: '/overlay/tokens' },
          { text: 'Signal Tiles & What They Mean', link: '/overlay/signals' },
          { text: 'Candidate Consent', link: '/overlay/consent' },
        ],
      },
      {
        text: 'Self-Hosting & Operations',
        collapsed: false,
        items: [
          { text: 'Docker Deployment', link: '/self-hosting/docker' },
          { text: 'Configuration & .env', link: '/self-hosting/environment' },
          { text: 'Preflight & /readyz', link: '/self-hosting/preflight' },
          { text: 'Postgres & Migrations', link: '/self-hosting/postgres' },
        ],
      },
      {
        text: 'Security & Reference',
        collapsed: false,
        items: [
          { text: 'Security & Privacy Model', link: '/reference/security' },
          { text: 'Limitations & Responsibilities', link: '/reference/limitations' },
          { text: 'AI Models & Licences', link: '/reference/models' },
          { text: 'REST API Reference', link: '/reference/api' },
          { text: 'Interactive Sandbox', link: '/reference/sandbox' },
          { text: 'FAQ & Changelog', link: '/reference/faq' },
        ],
      },
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/wequgy/RyouU' },
    ],
    search: {
      provider: 'local',
    },
    footer: {
      message: 'Layered, server-enforced identity verification & live interview integrity monitoring.',
      copyright: 'Copyright © 2026 RyouU Team. Open-source core under MIT and Apache 2.0.',
    },
  },
});

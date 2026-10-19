import DefaultTheme from 'vitepress/theme';
import type { Theme } from 'vitepress';
import './custom.css';
import Layout from './Layout.vue';
import LandingPage from './components/LandingPage.vue';
import SandboxSimulator from './components/SandboxSimulator.vue';

export default {
  extends: DefaultTheme,
  Layout,
  enhanceApp({ app }) {
    app.component('LandingPage', LandingPage);
    app.component('SandboxSimulator', SandboxSimulator);
  },
} satisfies Theme;


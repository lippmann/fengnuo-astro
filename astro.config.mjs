import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://fengnuo.me',
  output: 'static',
  integrations: [sitemap()],
});

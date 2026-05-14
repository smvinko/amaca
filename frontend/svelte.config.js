import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
export default {
  preprocess: vitePreprocess(),
  kit: {
    // SPA mode: prerender nothing, fallback to index.html for client-side routing.
    adapter: adapter({ fallback: 'index.html' }),
    prerender: { entries: [] }
  }
};

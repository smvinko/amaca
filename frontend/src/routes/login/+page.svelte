<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import { refreshUser } from '$lib/auth';
  import { goto } from '$app/navigation';

  let devLoginAvailable = $state(false);
  let devUsername = $state('dev');
  let busy = $state(false);
  let error = $state('');

  onMount(async () => {
    // Probe dev-login: only enabled when the backend has AMACA_DEV_LOGIN set.
    try {
      const r = await fetch('/api/auth/dev-login', { method: 'OPTIONS' });
      devLoginAvailable = r.status !== 404;
    } catch { /* leave false */ }
  });

  async function doDevLogin() {
    busy = true; error = '';
    try {
      await api.devLogin(devUsername.trim() || 'dev');
      await refreshUser();
      goto('/');
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }
</script>

<h2>Sign in</h2>

<div class="card">
  <p>amaca uses GitHub to authenticate. Click below to start the OAuth flow.</p>
  <p><a class="button primary" href="/api/auth/login">Sign in with GitHub</a></p>
  <p class="muted">
    Your GitHub username must appear in the backend's <code>AMACA_ALLOWED_GITHUB_USERS</code> allowlist.
  </p>
</div>

{#if devLoginAvailable}
  <div class="card">
    <h3 style="margin-top:0">Dev login</h3>
    <p class="muted">
      The backend has <code>AMACA_DEV_LOGIN=1</code> set — auth a local user without going through GitHub.
    </p>
    <div class="row">
      <input bind:value={devUsername} placeholder="username" />
      <button class="primary" onclick={doDevLogin} disabled={busy}>
        {busy ? 'Signing in…' : 'Dev sign in'}
      </button>
    </div>
    {#if error}<p class="danger">{error}</p>{/if}
  </div>
{/if}

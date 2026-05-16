<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';
  import { user, refreshUser, logout } from '$lib/auth';
  import { goto } from '$app/navigation';

  let { children }: { children: Snippet } = $props();

  onMount(() => { refreshUser(); });

  async function handleLogout() {
    await logout();
    goto('/login');
  }
</script>

<header class="appbar">
  <h1><a href="/">amaca</a></h1>
  <nav>
    {#if $user === undefined}
      <span class="muted">…</span>
    {:else if $user === null}
      <a href="/login">Sign in</a>
    {:else}
      <span class="muted">{$user.github_username}{#if $user.role === 'admin'} · admin{/if}</span>
      <button onclick={handleLogout}>Sign out</button>
    {/if}
  </nav>
</header>

<main class="container">
  {@render children?.()}
</main>

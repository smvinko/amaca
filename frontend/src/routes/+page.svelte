<script lang="ts">
  import { onMount } from 'svelte';
  import { user } from '$lib/auth';
  import { goto } from '$app/navigation';

  let timer: ReturnType<typeof setTimeout> | null = null;

  // Once we know the auth state, route accordingly. Codes-list page
  // arrives in the next commit; for now signed-in users see a placeholder.
  $: if ($user === null) goto('/login');
</script>

{#if $user === undefined}
  <p class="muted">Loading…</p>
{:else if $user}
  <h2>Welcome, {$user.github_username}</h2>
  <p class="muted">The codes list and job submission pages arrive next. For now the API is reachable at <a href="/api/docs">/api/docs</a>.</p>
{/if}

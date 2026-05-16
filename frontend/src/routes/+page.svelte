<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { user } from '$lib/auth';
  import { api, type CodeOut } from '$lib/api';

  let codes = $state<CodeOut[] | null>(null);
  let error = $state('');

  onMount(load);

  async function load() {
    if ($user === null) { goto('/login'); return; }
    if ($user === undefined) return;     // layout is still loading the user
    try {
      codes = await api.listCodes();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  // Re-load once the auth store resolves.
  $effect(() => {
    if ($user) load();
    else if ($user === null) goto('/login');
  });
</script>

<h2>Codes</h2>

{#if error}
  <p class="danger">{error}</p>
{/if}

{#if codes === null}
  <p class="muted">Loading…</p>
{:else if codes.length === 0}
  <p class="muted">No codes registered.</p>
{:else}
  {#each codes as code}
    <a class="card code-card" href="/codes/{encodeURIComponent(code.name)}">
      <div class="row" style="justify-content: space-between; align-items: baseline">
        <strong>{code.title}</strong>
        <span class="muted">{code.name} · v{code.version}</span>
      </div>
      {#if code.input_schema.description}
        <p class="muted" style="margin: 0.5rem 0 0">{code.input_schema.description}</p>
      {/if}
    </a>
  {/each}
{/if}

<p style="margin-top: 1.5rem"><a href="/jobs">My jobs →</a></p>

<style>
  .code-card { display: block; text-decoration: none; color: inherit; }
  .code-card:hover { border-color: var(--accent); }
</style>

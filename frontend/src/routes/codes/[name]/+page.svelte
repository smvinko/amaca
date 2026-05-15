<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { api, type CodeOut, ApiError } from '$lib/api';
  import FormField from '$lib/FormField.svelte';

  let code: CodeOut | null = null;
  let values: Record<string, unknown> = {};
  let loadError = '';
  let submitError = '';
  let busy = false;
  // Don't persist to localStorage until we've finished restoring (avoids
  // a brief window where partial state would clobber the saved snapshot).
  let storageReady = false;

  $: name = $page.params.name;
  $: storageKey = `amaca:inputs:${name}`;

  onMount(load);

  async function load() {
    try {
      code = await api.getCode(name);
      const props = code.input_schema.properties ?? {};
      // Schema defaults first.
      const defaults = Object.fromEntries(
        Object.entries(props).map(([k, p]) => [k, (p as { default?: unknown }).default])
      );
      // Then overlay any values the user persisted from a previous visit
      // (only for keys that still exist in the schema).
      const saved = readSaved();
      for (const k of Object.keys(defaults)) {
        if (saved && Object.prototype.hasOwnProperty.call(saved, k)) {
          defaults[k] = saved[k];
        }
      }
      values = defaults;
      storageReady = true;
    } catch (e) {
      loadError = e instanceof Error ? e.message : String(e);
    }
  }

  function readSaved(): Record<string, unknown> | null {
    if (typeof localStorage === 'undefined') return null;
    try {
      const raw = localStorage.getItem(storageKey);
      return raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
    } catch {
      return null;
    }
  }

  // Persist every change. Skipped until storageReady so the initial
  // load doesn't immediately overwrite the saved snapshot with the
  // schema-default seed.
  $: if (storageReady && typeof localStorage !== 'undefined') {
    try { localStorage.setItem(storageKey, JSON.stringify(values)); } catch { /* quota etc. */ }
  }

  function resetDefaults() {
    if (!code) return;
    const props = code.input_schema.properties ?? {};
    values = Object.fromEntries(
      Object.entries(props).map(([k, p]) => [k, (p as { default?: unknown }).default])
    );
    try { localStorage.removeItem(storageKey); } catch { /* ignore */ }
  }

  async function submit() {
    if (!code) return;
    busy = true; submitError = '';
    try {
      const job = await api.submitJob(code.name, values);
      goto(`/jobs/${job.id}`);
    } catch (e) {
      if (e instanceof ApiError && Array.isArray(e.body)) {
        submitError = e.body
          .map((err: any) => `${err.loc?.join('.') ?? ''}: ${err.msg}`)
          .join('\n');
      } else {
        submitError = e instanceof Error ? e.message : String(e);
      }
    } finally {
      busy = false;
    }
  }
</script>

<p><a href="/">← all codes</a></p>

{#if loadError}
  <p class="danger">{loadError}</p>
{:else if code === null}
  <p class="muted">Loading…</p>
{:else}
  <h2>{code.title}</h2>
  <p class="muted">{code.name} · v{code.version}</p>

  <div class="card">
    {#each Object.entries(code.input_schema.properties ?? {}) as [fieldName, fieldSchema]}
      <FormField
        name={fieldName}
        schema={fieldSchema}
        bind:value={values[fieldName]}
      />
    {/each}

    {#if submitError}
      <pre class="danger" style="margin: 0.5rem 0; white-space: pre-wrap">{submitError}</pre>
    {/if}

    <div class="row" style="margin-top: 0.5rem; justify-content: space-between">
      <div class="row">
        <button class="primary" on:click={submit} disabled={busy}>
          {busy ? 'Submitting…' : 'Submit'}
        </button>
        <a href="/" class="muted">cancel</a>
      </div>
      <button type="button" on:click={resetDefaults} title="Restore schema defaults and forget this browser's saved values">
        Reset to defaults
      </button>
    </div>
  </div>
{/if}

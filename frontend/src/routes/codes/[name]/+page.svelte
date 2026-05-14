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

  $: name = $page.params.name;

  onMount(load);

  async function load() {
    try {
      code = await api.getCode(name);
      // Pre-fill values from each property's default (if any).
      const props = code.input_schema.properties ?? {};
      values = Object.fromEntries(
        Object.entries(props).map(([k, p]) => [k, (p as { default?: unknown }).default])
      );
    } catch (e) {
      loadError = e instanceof Error ? e.message : String(e);
    }
  }

  async function submit() {
    if (!code) return;
    busy = true; submitError = '';
    try {
      const job = await api.submitJob(code.name, values);
      goto(`/jobs/${job.id}`);
    } catch (e) {
      if (e instanceof ApiError && Array.isArray(e.body)) {
        // Pydantic validation error array
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

    <div class="row" style="margin-top: 0.5rem">
      <button class="primary" on:click={submit} disabled={busy}>
        {busy ? 'Submitting…' : 'Submit'}
      </button>
      <a href="/" class="muted">cancel</a>
    </div>
  </div>
{/if}

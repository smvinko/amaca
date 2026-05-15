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

  // Resolve the form's groups: take the schema's x-input-groups list,
  // keep only the fields that actually exist, then put any leftover
  // properties in an "Other" group at the end. Fields whose
  // x-show-when predicate isn't met against current `values` are
  // filtered out per render — this is what makes spectrum_* fields
  // pop in only when `generate_spectrum` is on.
  function fieldVisible(name: string): boolean {
    if (!code) return true;
    const prop = code.input_schema.properties?.[name];
    const swh = prop?.['x-show-when'];
    if (!swh || typeof swh !== 'object') return true;
    const want = swh.equals;
    const got = values[swh.field];
    return got === want;
  }

  $: groups = (() => {
    if (!code) return [];
    const props = code.input_schema.properties ?? {};
    const declared = code.input_schema['x-input-groups'] ?? [];
    const seen = new Set<string>();
    const out: { title: string | null; fields: string[] }[] = [];
    // values is read inside fieldVisible — referencing it here makes
    // Svelte's reactivity rerun when the user toggles a gating field.
    void values;
    for (const g of declared) {
      const fields = g.fields.filter((f) => f in props && fieldVisible(f));
      if (fields.length === 0) continue;
      g.fields.forEach((f) => seen.add(f));   // mark gated-but-declared as "claimed"
      out.push({ title: g.title, fields });
    }
    const leftover = Object.keys(props).filter((f) => !seen.has(f) && fieldVisible(f));
    if (leftover.length > 0) {
      out.push({ title: declared.length === 0 ? null : 'Other', fields: leftover });
    }
    return out;
  })();

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

  <div class="form">
    {#each groups as group}
      <section class="group">
        {#if group.title}
          <h3 class="group-title">{group.title}</h3>
        {/if}
        <div class="group-fields">
          {#each group.fields as fieldName}
            {@const fieldSchema = code.input_schema.properties?.[fieldName]}
            {#if fieldSchema}
              <FormField
                name={fieldName}
                schema={fieldSchema}
                bind:value={values[fieldName]}
              />
            {/if}
          {/each}
        </div>
      </section>
    {/each}

    {#if submitError}
      <pre class="danger" style="margin: 0.5rem 0; white-space: pre-wrap">{submitError}</pre>
    {/if}

    <div class="row" style="margin-top: 1rem; justify-content: space-between">
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

<style>
  .form { display: flex; flex-direction: column; gap: 1rem; }
  .group {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.85rem 1.1rem 0.4rem;
  }
  .group-title {
    margin: 0 0 0.65rem;
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--fg-muted);
  }
  .group-fields {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.5rem;
  }
  /* Fields share the row evenly with a soft min-width so things wrap
     onto another line at narrow widths instead of squashing. */
  .group-fields > :global(.field) {
    flex: 1 1 14rem;
    margin-bottom: 0.6rem;
  }
</style>

<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { api, type CodeOut, ApiError } from '$lib/api';
  import FormField from '$lib/FormField.svelte';
  import GroupPlot from '$lib/GroupPlot.svelte';

  type GroupPlotSpec = {
    kind: string;
    title?: string;
    fields: Record<string, string>;
    x_label?: string;
    y_label?: string;
  };

  let code = $state<CodeOut | null>(null);
  let values = $state<Record<string, unknown>>({});
  let loadError = $state('');
  let submitError = $state('');
  let busy = $state(false);
  // Don't persist to localStorage until we've finished restoring (avoids
  // a brief window where partial state would clobber the saved snapshot).
  let storageReady = $state(false);

  const name = $derived($page.params.name as string);
  const storageKey = $derived(`amaca:inputs:${name}`);

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
  $effect(() => {
    if (storageReady && typeof localStorage !== 'undefined') {
      try { localStorage.setItem(storageKey, JSON.stringify(values)); } catch { /* quota etc. */ }
    }
  });

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
    const got = values[swh.field];
    if ('not_equals' in swh && swh.not_equals !== undefined) {
      return got !== swh.not_equals;
    }
    return got === swh.equals;
  }

  // A group renders as: `fields` (flow, full-width, declared order)
  // followed by `columns` (an explicit N-column block). A field
  // declared in `columns` is laid out there; everything else flows.
  type Group = {
    title: string | null;
    fields: string[];
    columns: string[][];
    plot: GroupPlotSpec | null;
  };

  const groups = $derived.by((): Group[] => {
    if (!code) return [];
    const props = code.input_schema.properties ?? {};
    const declared = code.input_schema['x-input-groups'] ?? [];
    const seen = new Set<string>();
    const out: Group[] = [];
    // values is read inside fieldVisible — referencing it here makes
    // Svelte's reactivity rerun when the user toggles a gating field.
    void values;
    const visible = (f: string) => f in props && fieldVisible(f);
    for (const g of declared) {
      const colDecl = g.columns ?? [];
      const inColumn = new Set(colDecl.flat());
      const fields = g.fields.filter((f) => !inColumn.has(f) && visible(f));
      const columns = colDecl
        .map((col) => col.filter(visible))
        .filter((col) => col.length > 0);
      // Preview plot shows only when every field it binds is visible
      // (so it falls away in modes where its inputs are gated off).
      const plot =
        g.plot && Object.values(g.plot.fields).every(visible)
          ? (g.plot as GroupPlotSpec)
          : null;
      if (fields.length === 0 && columns.length === 0 && !plot) continue;
      g.fields.forEach((f) => seen.add(f));   // mark gated-but-declared as "claimed"
      out.push({ title: g.title, fields, columns, plot });
    }
    const leftover = Object.keys(props).filter((f) => !seen.has(f) && fieldVisible(f));
    if (leftover.length > 0) {
      out.push({
        title: declared.length === 0 ? null : 'Other',
        fields: leftover, columns: [], plot: null
      });
    }
    return out;
  });

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

  {#snippet fieldCtl(fieldName: string)}
    {@const fieldSchema = code?.input_schema.properties?.[fieldName]}
    {#if fieldSchema}
      <FormField
        name={fieldName}
        schema={fieldSchema}
        bind:value={values[fieldName]}
      />
    {/if}
  {/snippet}

  <div class="form">
    {#each groups as group}
      <section class="group">
        {#if group.title}
          <h3 class="group-title">{group.title}</h3>
        {/if}
        {#if group.fields.length > 0}
          <div class="group-fields">
            {#each group.fields as fieldName}
              {@render fieldCtl(fieldName)}
              {#if code?.input_schema.properties?.[fieldName]?.['x-row-break']}
                <div class="row-break"></div>
              {/if}
            {/each}
          </div>
        {/if}
        {#if group.columns.length > 0}
          <div
            class="group-columns"
            style="grid-template-columns: repeat({group.columns.length}, minmax(0, 1fr))"
          >
            {#each group.columns as col}
              <div class="group-col">
                {#each col as fieldName}
                  {@render fieldCtl(fieldName)}
                {/each}
              </div>
            {/each}
          </div>
        {/if}
        {#if group.plot}
          <GroupPlot plot={group.plot} {values} />
        {/if}
      </section>
    {/each}

    {#if submitError}
      <pre class="danger" style="margin: 0.5rem 0; white-space: pre-wrap">{submitError}</pre>
    {/if}

    <div class="row" style="margin-top: 1rem; justify-content: space-between">
      <div class="row">
        <button class="primary" onclick={submit} disabled={busy}>
          {busy ? 'Submitting…' : 'Submit'}
        </button>
        <a href="/" class="muted">cancel</a>
      </div>
      <button type="button" onclick={resetDefaults} title="Restore schema defaults and forget this browser's saved values">
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
  /* x-row-break: a zero-height full-width flex item forces the next
     fields onto a new line, so the row ends right after the field
     it follows (which still shares its row with earlier siblings). */
  .group-fields > .row-break {
    flex: 0 0 100%;
    height: 0;
    margin: 0;
  }
  /* Fields share the row evenly with a soft min-width so things wrap
     onto another line at narrow widths instead of squashing. */
  .group-fields > :global(.field) {
    flex: 1 1 14rem;
    margin-bottom: 0.6rem;
  }
  /* A field marked x-full-row claims the whole row (and forces a
     wrap), so a gating selector always sits alone and everything
     revealed after it stacks below — at any window width. */
  .group-fields > :global(.field.full-row) {
    flex: 1 0 100%;
  }
  /* Explicit multi-column block (x-input-groups[].columns). Sits below
     any full-width flow fields in the same group. */
  .group-columns {
    display: grid;
    gap: 0.1rem 1.5rem;
    margin-top: 0.35rem;
  }
  .group-col {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .group-col > :global(.field) {
    margin-bottom: 0.6rem;
  }
</style>

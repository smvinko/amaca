<script lang="ts">
  /**
   * Generic form field driven by one entry in a JSON-Schema `properties` map.
   * Handles the property kinds pydantic v2 emits: integer/number/string/boolean
   * with optional min/max constraints, plus enum-style fields (Literal[...])
   * surfaced either as `enum: [...]` or `anyOf: [{const: ...}, ...]`.
   */
  import type { JsonSchemaProperty } from './api';

  export let name: string;
  export let schema: JsonSchemaProperty;
  export let value: unknown;

  // Detect enum options (either form pydantic uses).
  function enumOptions(s: JsonSchemaProperty): unknown[] | null {
    if (Array.isArray(s.enum)) return s.enum;
    if (Array.isArray(s.anyOf)) {
      const consts = s.anyOf
        .map((b) => (b && typeof b === 'object' && 'const' in b ? b.const : undefined))
        .filter((v) => v !== undefined);
      if (consts.length === s.anyOf.length) return consts;
    }
    return null;
  }

  $: options = enumOptions(schema);
  $: typeStr = (schema.type ?? '').toString();
  $: minVal =
    (typeof schema.minimum === 'number' ? schema.minimum :
     typeof schema.exclusiveMinimum === 'number' ? schema.exclusiveMinimum + (typeStr === 'integer' ? 1 : 1e-12) :
     undefined);
  $: maxVal =
    (typeof schema.maximum === 'number' ? schema.maximum :
     typeof schema.exclusiveMaximum === 'number' ? schema.exclusiveMaximum - (typeStr === 'integer' ? 1 : 1e-12) :
     undefined);
  $: stepVal = typeStr === 'integer' ? 1 : 'any';

  function coerce(raw: string): unknown {
    if (typeStr === 'integer') return raw === '' ? undefined : Math.trunc(Number(raw));
    if (typeStr === 'number')  return raw === '' ? undefined : Number(raw);
    return raw;
  }

  function onInput(ev: Event) {
    const target = ev.target as HTMLInputElement | HTMLSelectElement;
    value = coerce(target.value);
  }

  function onBool(ev: Event) {
    value = (ev.target as HTMLInputElement).checked;
  }

  // Lifted casts (Svelte 4's template parser doesn't allow `as` inside attribute exprs)
  $: numericValue = typeof value === 'number' ? value : ('' as const);
  $: stringValue  = typeof value === 'string' ? value : '';
  $: boolValue    = Boolean(value);
</script>

<label class="field">
  <span class="field-label">{schema.title ?? name}</span>
  {#if schema.description}
    <span class="field-help">{schema.description}</span>
  {/if}

  {#if options}
    <select on:change={onInput}>
      {#each options as opt}
        <option value={String(opt)} selected={opt === value}>{opt}</option>
      {/each}
    </select>
  {:else if typeStr === 'boolean'}
    <input type="checkbox" checked={boolValue} on:change={onBool} />
  {:else if typeStr === 'integer' || typeStr === 'number'}
    <input
      type="number"
      value={numericValue}
      min={minVal}
      max={maxVal}
      step={stepVal}
      on:input={onInput}
    />
  {:else}
    <input
      type="text"
      value={stringValue}
      minlength={schema.minLength}
      maxlength={schema.maxLength}
      on:input={onInput}
    />
  {/if}
</label>

<style>
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    margin-bottom: 0.85rem;
  }
  .field-label {
    font-weight: 500;
  }
  .field-help {
    color: var(--fg-muted);
    font-size: 0.9em;
  }
</style>

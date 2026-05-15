<script lang="ts">
  /**
   * Generic form field driven by one entry in a JSON-Schema `properties` map.
   * Renders:
   *   - enum-style fields (oneOf / enum / anyOf) → wrapped button group
   *   - boolean → checkbox + On/Off label
   *   - integer / number → plain HTML number input (with policy min/max if set)
   *   - everything else → text input
   *
   * Per-field display-unit conversion is honoured: a schema entry of the form
   *   "x-display-unit": { factor: 1e-15, label: "fs" }
   * makes the user type/edit in `label` units while the bound (stored) value
   * stays in the native unit (the input × factor).
   */
  import type { JsonSchemaProperty } from './api';

  export let name: string;
  export let schema: JsonSchemaProperty;
  export let value: unknown;

  function enumOptions(
    s: JsonSchemaProperty
  ): { value: unknown; label: string }[] | null {
    if (Array.isArray(s.oneOf) && s.oneOf.every((b) => b && 'const' in b)) {
      return s.oneOf.map((b) => ({
        value: b.const,
        label: b.title ?? String(b.const)
      }));
    }
    if (Array.isArray(s.enum)) {
      return s.enum.map((v) => ({ value: v, label: String(v) }));
    }
    if (Array.isArray(s.anyOf)) {
      const consts = s.anyOf.filter(
        (b) => b && typeof b === 'object' && 'const' in b
      );
      if (consts.length === s.anyOf.length) {
        return consts.map((b) => ({ value: b.const, label: String(b.const) }));
      }
    }
    return null;
  }

  $: options = enumOptions(schema);
  $: typeStr = (schema.type ?? '').toString();
  $: rawMin =
    (typeof schema.minimum === 'number' ? schema.minimum :
     typeof schema.exclusiveMinimum === 'number' ? schema.exclusiveMinimum + (typeStr === 'integer' ? 1 : 1e-12) :
     undefined);
  $: rawMax =
    (typeof schema.maximum === 'number' ? schema.maximum :
     typeof schema.exclusiveMaximum === 'number' ? schema.exclusiveMaximum - (typeStr === 'integer' ? 1 : 1e-12) :
     undefined);

  // x-display-unit: user types in `label` units, value is stored in
  // native units (= input × factor).
  $: displayUnit = (schema as Record<string, unknown>)['x-display-unit'] as
    | { factor: number; label: string }
    | undefined;
  $: factor = displayUnit?.factor ?? 1;
  $: unitLabel = displayUnit?.label ?? '';

  $: displayValue =
    typeof value === 'number' ? value / factor : ('' as const);
  $: displayMin = typeof rawMin === 'number' ? rawMin / factor : undefined;
  $: displayMax = typeof rawMax === 'number' ? rawMax / factor : undefined;
  $: stepVal = typeStr === 'integer' ? 1 : 'any';

  function onNumberInput(ev: Event) {
    const target = ev.target as HTMLInputElement;
    const raw = target.value;
    if (raw === '') { value = undefined; return; }
    const n = typeStr === 'integer' ? Math.trunc(Number(raw)) : Number(raw);
    value = n * factor;
  }

  function onTextInput(ev: Event) {
    value = (ev.target as HTMLInputElement).value;
  }

  function onBool(ev: Event) {
    value = (ev.target as HTMLInputElement).checked;
  }

  function pickOption(v: unknown) {
    value = v;
  }

  $: stringValue = typeof value === 'string' ? value : '';
  $: boolValue   = Boolean(value);
</script>

<div class="field">
  <span class="field-label">{schema.title ?? name}</span>
  {#if schema.description}
    <span class="field-help">{schema.description}</span>
  {/if}

  {#if options}
    <div class="option-group" role="radiogroup">
      {#each options as opt}
        <button
          type="button"
          class="option-button"
          class:active={opt.value === value}
          aria-pressed={opt.value === value}
          on:click={() => pickOption(opt.value)}
        >
          {opt.label}
        </button>
      {/each}
    </div>
  {:else if typeStr === 'boolean'}
    <label class="toggle">
      <input type="checkbox" checked={boolValue} on:change={onBool} />
      <span class="toggle-text">{boolValue ? 'On' : 'Off'}</span>
    </label>
  {:else if typeStr === 'integer' || typeStr === 'number'}
    <div class="num-row">
      <input
        type="number"
        value={displayValue}
        min={displayMin}
        max={displayMax}
        step={stepVal}
        on:input={onNumberInput}
      />
      {#if unitLabel}
        <span class="unit-label">{unitLabel}</span>
      {/if}
    </div>
  {:else}
    <input
      type="text"
      value={stringValue}
      minlength={schema.minLength}
      maxlength={schema.maxLength}
      on:input={onTextInput}
    />
  {/if}
</div>

<style>
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    margin-bottom: 0.85rem;
  }
  .field-label { font-weight: 500; }
  .field-help { color: var(--fg-muted); font-size: 0.9em; }

  .option-group {
    display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.15rem;
  }
  .option-button {
    padding: 0.35rem 0.75rem;
    min-width: 2.5rem;
    border: 1px solid var(--border);
    background: var(--bg-elev);
    color: var(--fg);
    border-radius: 6px;
    cursor: pointer;
    font-size: inherit;
    font-family: inherit;
    transition: background 0.1s, border-color 0.1s, color 0.1s;
  }
  .option-button:hover:not(.active) {
    border-color: var(--accent);
    color: var(--accent);
  }
  .option-button.active {
    background: var(--accent);
    color: #0a0d12;
    border-color: var(--accent);
    font-weight: 500;
  }

  .toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    user-select: none;
  }
  .toggle input { width: 1.1rem; height: 1.1rem; }
  .toggle-text { font-size: 0.95em; }

  .num-row {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }
  .num-row input { width: 10rem; }
  .unit-label {
    color: var(--fg-muted);
    font-weight: 500;
    font-family: var(--font-mono);
  }
</style>

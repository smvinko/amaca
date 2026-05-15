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

  // Format a numeric display value. Floating-point noise (e.g. 1.21e-13 ÷
  // 1e-15 = 121.00000000000001) is dropped by rounding through 12 sig
  // figs. Plain string for "normal" magnitudes; clean exponential (no
  // "+") for very large or very small numbers.
  function fmtNumber(n: number | undefined | null): string {
    if (typeof n !== 'number' || !isFinite(n)) return '';
    if (n === 0) return '0';
    const clean = Number(n.toPrecision(12));   // strip FP noise
    const abs = Math.abs(clean);
    if (abs >= 1e6 || abs < 1e-3) {
      return clean.toExponential().replace('e+', 'e');
    }
    return String(clean);
  }

  // Local text state for the numeric field. We use <input type=text>
  // (not type=number) because:
  //   - the browser's "number" input rejects intermediate sci-notation
  //     ("1e" is invalid until you finish typing the exponent)
  //   - max="1e22" attributes interact weirdly with very-large values
  // We parse on every keystroke; invalid mid-states just leave the
  // bound `value` unchanged until the text parses to a finite number.
  let numText = '';
  let numInitialised = false;

  $: {
    // Sync FROM the bound value when it changes for a reason OTHER than
    // our own keystroke (e.g. initial mount, policy clamp on resubmit).
    const parsed = numText.trim() === '' ? undefined : Number(numText);
    const native =
      typeof parsed === 'number' && isFinite(parsed)
        ? (typeStr === 'integer' ? Math.trunc(parsed) : parsed) * factor
        : undefined;
    if (!numInitialised || (typeof value === 'number' && value !== native)) {
      numText = typeof value === 'number' ? fmtNumber(value / factor) : '';
      numInitialised = true;
    }
  }

  $: displayMin = typeof rawMin === 'number' ? fmtNumber(rawMin / factor) : '';
  $: displayMax = typeof rawMax === 'number' ? fmtNumber(rawMax / factor) : '';

  function onNumberInput(ev: Event) {
    numText = (ev.target as HTMLInputElement).value;
    const raw = numText.trim();
    if (raw === '') { value = undefined; return; }
    const n = Number(raw);
    if (!isFinite(n)) return;        // mid-typing; wait for valid input
    if (typeStr === 'integer' && !Number.isInteger(n)) {
      // Decimal value entered into an integer field — reject and let the
      // .invalid class surface the issue.
      return;
    }
    value = n * factor;
  }

  function onTextInput(ev: Event) {
    value = (ev.target as HTMLInputElement).value;
  }

  // Block "." / "," keystrokes on integer fields so users can't even
  // type a decimal in the first place.
  function blockDecimalKey(ev: KeyboardEvent) {
    if (typeStr === 'integer' && (ev.key === '.' || ev.key === ',')) {
      ev.preventDefault();
    }
  }
  function blockDecimalPaste(ev: ClipboardEvent) {
    if (typeStr !== 'integer') return;
    const text = ev.clipboardData?.getData('text') ?? '';
    if (text.includes('.') || text.includes(',')) ev.preventDefault();
  }

  // Validity flag drives the .invalid class — covers paste-then-edit
  // and the brief mid-typing window before onNumberInput's coercion.
  $: numTextValid = (() => {
    const raw = numText.trim();
    if (raw === '') return true;
    const n = Number(raw);
    if (!isFinite(n)) return false;
    if (typeStr === 'integer' && !Number.isInteger(n)) return false;
    return true;
  })();

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
        type="text"
        inputmode={typeStr === 'integer' ? 'numeric' : 'decimal'}
        autocomplete="off"
        spellcheck={false}
        class:invalid={!numTextValid}
        value={numText}
        on:input={onNumberInput}
        on:keydown={blockDecimalKey}
        on:paste={blockDecimalPaste}
      />
      {#if unitLabel}
        <span class="unit-label">{unitLabel}</span>
      {/if}
      {#if displayMin !== '' || displayMax !== ''}
        <span class="range-hint">range: {displayMin || '−∞'}…{displayMax || '+∞'}</span>
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
  .num-row input { width: 10rem; font-family: var(--font-mono); }
  .num-row input.invalid {
    border-color: var(--danger);
    color: var(--danger);
  }
  .unit-label {
    color: var(--fg-muted);
    font-weight: 500;
    font-family: var(--font-mono);
  }
  .range-hint {
    color: var(--fg-muted);
    font-size: 0.8em;
    font-family: var(--font-mono);
  }
</style>

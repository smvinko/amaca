<script lang="ts">
  /**
   * Renders an enum of chemical-element symbols as a real periodic
   * table (periods 1–4 / Z = 1–36). Driven entirely by the field's
   * `oneOf` options — only symbols present in `options` are active
   * buttons; every other cell stays blank so the table keeps its
   * familiar shape (H/He split, the d-block gap, …).
   *
   * Generic amaca widget: triggered by `x-widget: "periodic-table"` on
   * any string field whose options are element symbols. Anything not in
   * the Z=1–36 map falls back to a plain button row beneath the table,
   * so a mis-tagged field degrades gracefully instead of vanishing.
   */
  type Opt = { value: unknown; label: string };

  let {
    options,
    value = $bindable()
  }: {
    options: Opt[];
    value: unknown;
  } = $props();

  // symbol → { z, period (row), group (column 1–18) }, periods 1–4.
  const PT: Record<string, { z: number; period: number; group: number }> = {
    H:  { z: 1,  period: 1, group: 1  }, He: { z: 2,  period: 1, group: 18 },
    Li: { z: 3,  period: 2, group: 1  }, Be: { z: 4,  period: 2, group: 2  },
    B:  { z: 5,  period: 2, group: 13 }, C:  { z: 6,  period: 2, group: 14 },
    N:  { z: 7,  period: 2, group: 15 }, O:  { z: 8,  period: 2, group: 16 },
    F:  { z: 9,  period: 2, group: 17 }, Ne: { z: 10, period: 2, group: 18 },
    Na: { z: 11, period: 3, group: 1  }, Mg: { z: 12, period: 3, group: 2  },
    Al: { z: 13, period: 3, group: 13 }, Si: { z: 14, period: 3, group: 14 },
    P:  { z: 15, period: 3, group: 15 }, S:  { z: 16, period: 3, group: 16 },
    Cl: { z: 17, period: 3, group: 17 }, Ar: { z: 18, period: 3, group: 18 },
    K:  { z: 19, period: 4, group: 1  }, Ca: { z: 20, period: 4, group: 2  },
    Sc: { z: 21, period: 4, group: 3  }, Ti: { z: 22, period: 4, group: 4  },
    V:  { z: 23, period: 4, group: 5  }, Cr: { z: 24, period: 4, group: 6  },
    Mn: { z: 25, period: 4, group: 7  }, Fe: { z: 26, period: 4, group: 8  },
    Co: { z: 27, period: 4, group: 9  }, Ni: { z: 28, period: 4, group: 10 },
    Cu: { z: 29, period: 4, group: 11 }, Zn: { z: 30, period: 4, group: 12 },
    Ga: { z: 31, period: 4, group: 13 }, Ge: { z: 32, period: 4, group: 14 },
    As: { z: 33, period: 4, group: 15 }, Se: { z: 34, period: 4, group: 16 },
    Br: { z: 35, period: 4, group: 17 }, Kr: { z: 36, period: 4, group: 18 }
  };

  // Selectable options keyed by symbol, for quick lookup.
  const allowed = $derived(
    new Map(
      options
        .filter((o) => typeof o.value === 'string')
        .map((o) => [o.value as string, o])
    )
  );
  // Every element in periods 1–4 gets a cell; ones not in `allowed`
  // render as inert (disabled) squares so the table is always complete.
  const cells = $derived(
    Object.entries(PT).map(([sym, pos]) => ({
      sym,
      ...pos,
      opt: allowed.get(sym) ?? null
    }))
  );
  const overflow = $derived(
    options.filter((o) => !(typeof o.value === 'string' && o.value in PT))
  );

  const select = (v: unknown) => { value = v; };
</script>

<div class="pt" role="radiogroup" aria-label="Element">
  {#each cells as c (c.sym)}
    {#if c.opt}
      {@const opt = c.opt}
      <button
        type="button"
        class="pt-cell"
        class:active={opt.value === value}
        style="grid-column: {c.group}; grid-row: {c.period};"
        aria-pressed={opt.value === value}
        title={opt.label}
        onclick={() => select(opt.value)}
      >
        <span class="z">{c.z}</span>
        <span class="sym">{c.sym}</span>
      </button>
    {:else}
      <button
        type="button"
        class="pt-cell"
        disabled
        style="grid-column: {c.group}; grid-row: {c.period};"
        title="{c.sym} — not available for this code"
      >
        <span class="z">{c.z}</span>
        <span class="sym">{c.sym}</span>
      </button>
    {/if}
  {/each}
</div>

{#if overflow.length > 0}
  <div class="pt-overflow" role="radiogroup" aria-label="Other">
    {#each overflow as opt (opt.value)}
      <button
        type="button"
        class="pt-cell"
        class:active={opt.value === value}
        aria-pressed={opt.value === value}
        onclick={() => select(opt.value)}
      >
        <span class="sym">{opt.label}</span>
      </button>
    {/each}
  </div>
{/if}

<style>
  .pt {
    display: grid;
    grid-template-columns: repeat(18, minmax(2.1rem, 1fr));
    grid-auto-rows: 2.6rem;
    gap: 0.25rem;
    /* Keep the table's shape on narrow screens rather than squashing. */
    overflow-x: auto;
    padding-bottom: 0.15rem;
  }
  .pt-overflow {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.4rem;
  }
  .pt-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    line-height: 1;
    padding: 0.2rem 0;
    border: 1px solid var(--border);
    background: var(--bg-elev);
    color: var(--fg);
    border-radius: 5px;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.1s, border-color 0.1s, color 0.1s;
  }
  .pt-cell .z {
    font-size: 0.6rem;
    color: var(--fg-muted);
  }
  .pt-cell .sym {
    font-size: 0.95rem;
    font-weight: 600;
  }
  .pt-cell:not(:disabled):hover:not(.active) {
    border-color: var(--accent);
    color: var(--accent);
  }
  .pt-cell:not(:disabled):hover:not(.active) .z { color: var(--accent); }
  /* Elements outside this code's policy: shown for context, inert. */
  .pt-cell:disabled {
    cursor: default;
    opacity: 0.32;
    background: var(--bg);
  }
  .pt-cell.active {
    background: var(--accent);
    color: #0a0d12;
    border-color: var(--accent);
  }
  .pt-cell.active .z { color: #0a0d12; }
  .pt-overflow .pt-cell { padding: 0.35rem 0.7rem; }
</style>

<script lang="ts">
  /**
   * Generic outputs renderer. Pretty-prints the JSON; if the payload has
   * matched-length numeric `x` / `y` arrays, also renders a small inline
   * SVG line plot. Specialised renderers per code can come later via the
   * Code.render() hook from SPEC §2.
   */
  export let outputs: Record<string, unknown> | null | undefined;

  function isNumberArray(v: unknown): v is number[] {
    return Array.isArray(v) && v.every((x) => typeof x === 'number');
  }

  $: plot = (() => {
    if (!outputs) return null;
    const x = outputs.x, y = outputs.y;
    if (!isNumberArray(x) || !isNumberArray(y) || x.length !== y.length || x.length < 2) return null;
    const W = 640, H = 240, pad = 24;
    const xmin = Math.min(...x), xmax = Math.max(...x);
    const ymin = Math.min(...y), ymax = Math.max(...y);
    const sx = (xx: number) => pad + ((xx - xmin) / (xmax - xmin || 1)) * (W - 2 * pad);
    const sy = (yy: number) => H - pad - ((yy - ymin) / (ymax - ymin || 1)) * (H - 2 * pad);
    const d = x.map((xi, i) => `${i === 0 ? 'M' : 'L'} ${sx(xi).toFixed(2)} ${sy(y[i]).toFixed(2)}`).join(' ');
    return { W, H, pad, d, xmin, xmax, ymin, ymax };
  })();
</script>

{#if outputs}
  {#if plot}
    <div class="plot">
      <svg viewBox="0 0 {plot.W} {plot.H}" width="100%" preserveAspectRatio="xMidYMid meet">
        <!-- frame -->
        <rect x="0.5" y="0.5" width={plot.W - 1} height={plot.H - 1}
              fill="none" stroke="var(--border)" />
        <!-- zero line if applicable -->
        {#if plot.ymin < 0 && plot.ymax > 0}
          {@const y0 = plot.H - plot.pad - ((0 - plot.ymin) / (plot.ymax - plot.ymin || 1)) * (plot.H - 2 * plot.pad)}
          <line x1={plot.pad} y1={y0} x2={plot.W - plot.pad} y2={y0}
                stroke="var(--border)" stroke-dasharray="3 3" />
        {/if}
        <!-- curve -->
        <path d={plot.d} fill="none" stroke="var(--accent)" stroke-width="2" />
      </svg>
      <p class="muted" style="margin: 0.25rem 0 0; font-size: 0.85em;">
        x ∈ [{plot.xmin.toPrecision(4)}, {plot.xmax.toPrecision(4)}],
        y ∈ [{plot.ymin.toPrecision(4)}, {plot.ymax.toPrecision(4)}]
      </p>
    </div>
  {/if}

  <details open>
    <summary style="cursor: pointer; margin: 0.75rem 0;">raw outputs</summary>
    <pre>{JSON.stringify(outputs, null, 2)}</pre>
  </details>
{:else}
  <p class="muted">No outputs yet.</p>
{/if}

<style>
  .plot {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.5rem;
  }
</style>

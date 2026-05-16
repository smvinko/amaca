<script lang="ts">
  /**
   * Read-only preview plot rendered at the bottom of a form group
   * (driven by an `x-input-groups[].plot` schema annotation). Native
   * inline SVG — no chart library — same approach as OutputView.
   *
   * It reads the live form `values` (a Svelte $state proxy shared with
   * the parent), so the curve recomputes as the user edits the inputs.
   *
   * Registry of `kind`s:
   *   gaussian-pulse — I(t) = peak·exp(−4 ln2 (t−center)² / fwhm²)
   *                    over t ∈ [0, t_max]. roles: peak, center,
   *                    fwhm, t_max.
   */
  type PlotSpec = {
    kind: string;
    title?: string;
    fields: Record<string, string>;
    x_label?: string;
    y_label?: string;
  };

  let {
    plot,
    values
  }: {
    plot: PlotSpec;
    values: Record<string, unknown>;
  } = $props();

  const num = (key: string | undefined): number => {
    const v = key ? values[key] : undefined;
    return typeof v === 'number' ? v : Number(v);
  };

  const fmt = (n: number): string =>
    n === 0 ? '0' : Number(n.toPrecision(4)).toExponential().replace('e+', 'e');

  // Recomputes whenever any referenced form value changes.
  const model = $derived.by(() => {
    if (plot.kind !== 'gaussian-pulse') return null;
    const f = plot.fields;
    const peak = num(f.peak);
    const t0 = num(f.center);
    const fwhm = num(f.fwhm);
    const tmax = num(f.t_max);
    if (
      ![peak, t0, fwhm, tmax].every((v) => Number.isFinite(v)) ||
      peak <= 0 || fwhm <= 0 || tmax <= 0
    ) {
      return null;
    }
    const N = 240;
    const k = (4 * Math.LN2) / (fwhm * fwhm);
    const xs: number[] = [];
    const ys: number[] = [];
    let ymax = 0;
    for (let i = 0; i < N; i++) {
      const t = (i / (N - 1)) * tmax;
      const I = peak * Math.exp(-k * (t - t0) * (t - t0));
      xs.push(t);
      ys.push(I);
      if (I > ymax) ymax = I;
    }
    if (ymax <= 0) ymax = peak;
    const W = 640, H = 200, pad = 26;
    const sx = (x: number) => pad + (x / (tmax || 1)) * (W - 2 * pad);
    const sy = (y: number) => H - pad - (y / (ymax || 1)) * (H - 2 * pad);
    const d = xs
      .map((x, i) => `${i === 0 ? 'M' : 'L'} ${sx(x).toFixed(2)} ${sy(ys[i]).toFixed(2)}`)
      .join(' ');
    const centerX = t0 >= 0 && t0 <= tmax ? sx(t0) : null;
    return { W, H, pad, d, centerX, tmax, ymax };
  });
</script>

<div class="group-plot">
  {#if plot.title}
    <h4 class="gp-title">{plot.title}</h4>
  {/if}
  {#if model}
    <svg
      viewBox="0 0 {model.W} {model.H}"
      width="100%"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={plot.title ?? 'preview plot'}
    >
      <rect
        x="0.5" y="0.5" width={model.W - 1} height={model.H - 1}
        fill="none" stroke="var(--border)"
      />
      {#if model.centerX !== null}
        <line
          x1={model.centerX} y1={model.pad}
          x2={model.centerX} y2={model.H - model.pad}
          stroke="var(--border)" stroke-dasharray="3 3"
        />
      {/if}
      <path d={model.d} fill="none" stroke="var(--accent)" stroke-width="2" />
    </svg>
    <p class="gp-cap muted">
      {plot.x_label ?? 'x'} ∈ [0, {fmt(model.tmax)}] · peak {fmt(model.ymax)}{plot.y_label
        ? ` ${plot.y_label}`
        : ''}
    </p>
  {:else}
    <p class="muted gp-empty">Enter valid pulse parameters to preview the shape.</p>
  {/if}
</div>

<style>
  .group-plot {
    margin-top: 0.6rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.6rem 0.7rem;
  }
  .gp-title {
    margin: 0 0 0.4rem;
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--fg-muted);
  }
  .gp-cap {
    margin: 0.3rem 0 0;
    font-size: 0.85em;
    font-family: var(--font-mono);
  }
  .gp-empty {
    margin: 0;
    font-size: 0.9em;
  }
</style>

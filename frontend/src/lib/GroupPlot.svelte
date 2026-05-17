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
    // Asymmetric padding: room on the left for y tick labels + the
    // rotated y-axis title, room at the bottom for x ticks + title.
    const W = 640, H = 220;
    const padL = 70, padR = 16, padT = 14, padB = 48;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;
    const sx = (x: number) => padL + (x / (tmax || 1)) * plotW;
    const sy = (y: number) => H - padB - (y / (ymax || 1)) * plotH;
    const d = xs
      .map((x, i) => `${i === 0 ? 'M' : 'L'} ${sx(x).toFixed(2)} ${sy(ys[i]).toFixed(2)}`)
      .join(' ');
    const centerX = t0 >= 0 && t0 <= tmax ? sx(t0) : null;
    // Evenly spaced ticks; labels via the shared exponential fmt().
    const NX = 4, NY = 4;
    const xticks = Array.from({ length: NX + 1 }, (_, i) => {
      const v = (i / NX) * tmax;
      return { px: sx(v), label: fmt(v) };
    });
    const yticks = Array.from({ length: NY + 1 }, (_, j) => {
      const v = (j / NY) * ymax;
      return { py: sy(v), label: fmt(v) };
    });
    return {
      W, H, padL, padR, padT, padB, d, centerX, tmax, ymax,
      xticks, yticks,
      axisX0: padL, axisX1: W - padR,
      axisY0: H - padB, axisY1: padT
    };
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
      <!-- y grid + tick labels -->
      {#each model.yticks as t}
        <line
          x1={model.axisX0} y1={t.py} x2={model.axisX1} y2={t.py}
          stroke="var(--border)" stroke-opacity="0.4"
        />
        <text
          x={model.axisX0 - 8} y={t.py + 3}
          text-anchor="end" class="gp-tick"
        >{t.label}</text>
      {/each}
      <!-- x ticks + tick labels -->
      {#each model.xticks as t}
        <line
          x1={t.px} y1={model.axisY0} x2={t.px} y2={model.axisY0 + 4}
          stroke="var(--fg-muted)"
        />
        <text
          x={t.px} y={model.axisY0 + 16}
          text-anchor="middle" class="gp-tick"
        >{t.label}</text>
      {/each}
      <!-- axes -->
      <line
        x1={model.axisX0} y1={model.axisY1}
        x2={model.axisX0} y2={model.axisY0}
        stroke="var(--fg-muted)"
      />
      <line
        x1={model.axisX0} y1={model.axisY0}
        x2={model.axisX1} y2={model.axisY0}
        stroke="var(--fg-muted)"
      />
      {#if model.centerX !== null}
        <line
          x1={model.centerX} y1={model.axisY1}
          x2={model.centerX} y2={model.axisY0}
          stroke="var(--border)" stroke-dasharray="3 3"
        />
      {/if}
      <path d={model.d} fill="none" stroke="var(--accent)" stroke-width="2" />
      <!-- axis titles -->
      <text
        x={(model.axisX0 + model.axisX1) / 2} y={model.H - 6}
        text-anchor="middle" class="gp-axis-title"
      >{plot.x_label ?? 'x'}</text>
      <text
        x="14" y={(model.axisY1 + model.axisY0) / 2}
        text-anchor="middle" class="gp-axis-title"
        transform="rotate(-90 14 {(model.axisY1 + model.axisY0) / 2})"
      >{plot.y_label ?? 'y'}</text>
    </svg>
    <p class="gp-cap muted">
      peak {fmt(model.ymax)}{plot.y_label ? ` ${plot.y_label}` : ''}
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
  .gp-tick {
    fill: var(--fg-muted);
    font-size: 11px;
    font-family: var(--font-mono);
  }
  .gp-axis-title {
    fill: var(--fg-muted);
    font-size: 12px;
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

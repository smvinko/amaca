<script lang="ts">
  /**
   * Generic native result figures. Driven by an output schema's
   * `x-output-plots` manifest: each entry becomes an inline-SVG figure
   * (no chart library), rendered one under the other from numeric
   * fields in the job `outputs`. Same hand-rolled SVG approach as
   * OutputView / GroupPlot — reusable by any code, not just ccfly.
   *
   * kind "lines":
   *   - `series`: explicit lines; axis 'left'|'right' gives a dual
   *     y-axis (e.g. Tₑ left, nₑ right).
   *   - `series_from`: a dict-valued output field → one line per entry
   *     (e.g. population per charge state), label `${series_label}${key}`.
   *
   * A figure with a single line shows no legend (it'd be redundant).
   * `y_scale_toggle: true` adds a little linear / log₁₀ switch beneath
   * the figure (per-figure, applies to both y-axes when dual).
   */
  type Spec = {
    kind: string;
    title?: string;
    x: string;
    x_label?: string;
    y_label?: string;
    series?: { y: string; label?: string; axis?: 'left' | 'right' }[];
    series_from?: string;
    series_label?: string;
    y_scale_toggle?: boolean;
  };

  let {
    plots,
    outputs
  }: {
    plots: Spec[];
    outputs: Record<string, unknown>;
  } = $props();

  const PALETTE = [
    'var(--accent)', '#e0567a', '#4fb286', '#d8913b', '#7d6cd6',
    '#3aa6c4', '#c45ab3', '#9aa23b', '#d06a4e', '#5a8fd6'
  ];

  // Per-figure y-axis scale: false = linear, true = log₁₀. Keyed by
  // the figure id; mutating it re-derives that figure.
  let yLog = $state<Record<string, boolean>>({});
  const figId = (s: Spec): string => s.title ?? s.x;

  const numArr = (v: unknown): number[] | null =>
    Array.isArray(v) && v.every((n) => typeof n === 'number')
      ? (v as number[])
      : null;

  const fmt = (n: number): string => {
    if (!isFinite(n)) return '–';
    if (n === 0) return '0';
    const a = Math.abs(n);
    return a >= 1e4 || a < 1e-3
      ? Number(n.toPrecision(3)).toExponential().replace('e+', 'e')
      : String(Number(n.toPrecision(4)));
  };

  /**
   * "Nice" axis ticks: round step from the 1 / 2 / 5 × 10ⁿ family so
   * labels land on meaningful values, count adapts to the range.
   */
  function niceTicks(lo: number, hi: number, target = 6): number[] {
    if (!isFinite(lo) || !isFinite(hi) || hi <= lo) return [lo];
    const raw = (hi - lo) / Math.max(1, target);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const n = raw / mag;
    const step = (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * mag;
    const start = Math.ceil(lo / step) * step;
    const ticks: number[] = [];
    for (let v = start; v <= hi + step * 1e-9 && ticks.length < 50; v += step) {
      ticks.push(Math.round(v / step) * step);
    }
    return ticks;
  }

  /** Decade ticks (powers of ten) across an exponent range, stepped
   *  so the count stays readable even over many decades. */
  function logTicks(elo: number, ehi: number): number[] {
    const step = Math.max(1, Math.ceil((ehi - elo) / 6));
    const ts: number[] = [];
    for (let e = elo; e <= ehi + 1e-9 && ts.length < 14; e += step) {
      ts.push(Math.pow(10, e));
    }
    const top = Math.pow(10, ehi);
    if (ts[ts.length - 1] !== top) ts.push(top);
    return ts;
  }

  type Line = { label: string; ys: number[]; color: string; right: boolean };
  type Range =
    | { log: false; lo: number; hi: number }
    | { log: true; lo: number; hi: number; elo: number; ehi: number };

  function build(spec: Spec, useLog: boolean) {
    const xs = numArr(outputs[spec.x]);
    if (!xs || xs.length < 2) return null;

    const lines: Line[] = [];
    if (spec.series) {
      spec.series.forEach((s, i) => {
        const ys = numArr(outputs[s.y]);
        if (ys && ys.length === xs.length) {
          lines.push({
            label: s.label ?? s.y,
            ys,
            color: PALETTE[i % PALETTE.length],
            right: s.axis === 'right'
          });
        }
      });
    } else if (spec.series_from) {
      const d = outputs[spec.series_from];
      if (d && typeof d === 'object' && !Array.isArray(d)) {
        const keys = Object.keys(d as Record<string, unknown>).sort(
          (a, b) => Number(a) - Number(b)
        );
        keys.forEach((k, i) => {
          const ys = numArr((d as Record<string, unknown>)[k]);
          if (ys && ys.length === xs.length) {
            lines.push({
              label: `${spec.series_label ?? ''}${k}`,
              ys,
              color: PALETTE[i % PALETTE.length],
              right: false
            });
          }
        });
      }
    }
    if (lines.length === 0) return null;

    const W = 660, H = 260, padL = 56, padR = 56, padT = 12, padB = 38;
    const plotH = H - padT - padB;
    const xmin = Math.min(...xs), xmax = Math.max(...xs);

    const rng = (sel: (l: Line) => boolean): Range | null => {
      const vals = lines.filter(sel).flatMap((l) => l.ys).filter(Number.isFinite);
      if (vals.length === 0) return null;
      if (useLog) {
        const pos = vals.filter((v) => v > 0);
        if (pos.length) {
          let elo = Math.floor(Math.log10(Math.min(...pos)));
          let ehi = Math.ceil(Math.log10(Math.max(...pos)));
          if (elo === ehi) { elo -= 1; ehi += 1; }
          return { log: true, elo, ehi, lo: 10 ** elo, hi: 10 ** ehi };
        }
        // no positive data on this axis → fall back to linear
      }
      let lo = Math.min(...vals), hi = Math.max(...vals);
      if (lo === hi) { lo -= 1; hi += 1; }
      return { log: false, lo, hi };
    };
    const left = rng((l) => !l.right);
    const right = rng((l) => l.right);
    const sx = (x: number) =>
      padL + ((x - xmin) / (xmax - xmin || 1)) * (W - padL - padR);
    const syOf = (r: Range) => (y: number) => {
      if (r.log) {
        const ly = Math.log10(Math.max(y, r.lo));
        return H - padB - ((ly - r.elo) / ((r.ehi - r.elo) || 1)) * plotH;
      }
      return H - padB - ((y - r.lo) / ((r.hi - r.lo) || 1)) * plotH;
    };
    const axTicks = (r: Range) =>
      (r.log
        ? logTicks(r.elo, r.ehi)
        : niceTicks(r.lo, r.hi, 5)
      ).map((v) => ({ v, py: syOf(r)(v) }));

    const paths = lines.map((l) => {
      const r = l.right ? right : left;
      if (!r) return null;
      const sy = syOf(r);
      return {
        d: l.ys
          .map((y, i) => `${i === 0 ? 'M' : 'L'} ${sx(xs[i]).toFixed(2)} ${sy(y).toFixed(2)}`)
          .join(' '),
        color: l.color,
        label: l.label,
        right: l.right
      };
    }).filter(Boolean) as { d: string; color: string; label: string; right: boolean }[];

    const xticks = niceTicks(xmin, xmax, 7).map((v) => ({ v, px: sx(v) }));
    const lyticks = left ? axTicks(left) : [];
    const ryticks = right ? axTicks(right) : [];

    return {
      W, H, padL, padR, padT, padB,
      xmin, xmax, left, right, paths,
      xticks, lyticks, ryticks,
      manyLines: lines.length > 6,
      showLegend: paths.length > 1
    };
  }

  const figures = $derived(
    plots
      .map((spec) => {
        const id = figId(spec);
        return { spec, id, m: build(spec, !!yLog[id]) };
      })
      .filter((f) => f.m)
  );
</script>

{#each figures as { spec, id, m } (id)}
  {#if m}
    <figure class="rp">
      {#if spec.title}<figcaption class="rp-title">{spec.title}</figcaption>{/if}
      <svg viewBox="0 0 {m.W} {m.H}" width="100%" preserveAspectRatio="xMidYMid meet"
           role="img" aria-label={spec.title ?? 'result figure'}>
        <!-- gridlines (x ticks + left-y ticks) -->
        {#each m.xticks as t}
          <line class="rp-grid" x1={t.px} y1={m.padT} x2={t.px} y2={m.H - m.padB} />
        {/each}
        {#each m.lyticks as t}
          <line class="rp-grid" x1={m.padL} y1={t.py} x2={m.W - m.padR} y2={t.py} />
        {/each}
        <rect x={m.padL} y={m.padT} width={m.W - m.padL - m.padR}
              height={m.H - m.padT - m.padB} fill="none" stroke="var(--border)" />
        {#each m.paths as p}
          <path d={p.d} fill="none" stroke={p.color} stroke-width="1.75" />
        {/each}
        <!-- x ticks -->
        {#each m.xticks as t}
          <line class="rp-axisln" x1={t.px} y1={m.H - m.padB} x2={t.px} y2={m.H - m.padB + 4} />
          <text x={t.px} y={m.H - m.padB + 16} class="rp-tick" text-anchor="middle">{fmt(t.v)}</text>
        {/each}
        {#if spec.x_label}
          <text x={(m.padL + m.W - m.padR) / 2} y={m.H - 4} class="rp-axis" text-anchor="middle">{spec.x_label}</text>
        {/if}
        <!-- left y ticks -->
        {#each m.lyticks as t}
          <line class="rp-axisln" x1={m.padL - 4} y1={t.py} x2={m.padL} y2={t.py} />
          <text x={m.padL - 7} y={t.py + 3} class="rp-tick" text-anchor="end">{fmt(t.v)}</text>
        {/each}
        <!-- right y ticks -->
        {#each m.ryticks as t}
          <line class="rp-axisln" x1={m.W - m.padR} y1={t.py} x2={m.W - m.padR + 4} y2={t.py} />
          <text x={m.W - m.padR + 7} y={t.py + 3} class="rp-tick">{fmt(t.v)}</text>
        {/each}
      </svg>
      {#if m.showLegend}
        <div class="rp-legend" class:compact={m.manyLines}>
          {#each m.paths as p}
            <span class="rp-key">
              <span class="rp-swatch" style="background:{p.color}"></span>{p.label}{#if p.right} <span class="rp-ax">(right)</span>{/if}
            </span>
          {/each}
        </div>
      {/if}
      {#if spec.y_scale_toggle}
        <div class="rp-scale">
          <button
            type="button"
            class="rp-scale-btn"
            aria-pressed={!!yLog[id]}
            onclick={() => (yLog[id] = !yLog[id])}
          >
            y-axis: {yLog[id] ? 'log₁₀' : 'linear'}
          </button>
        </div>
      {/if}
    </figure>
  {/if}
{/each}

<style>
  .rp {
    margin: 0 0 0.9rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.55rem 0.7rem 0.45rem;
  }
  .rp-title {
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--fg-muted);
    margin-bottom: 0.3rem;
  }
  :global(.rp svg .rp-tick) {
    font-size: 11px;
    fill: var(--fg-muted);
    font-family: var(--font-mono);
  }
  :global(.rp svg .rp-axis) {
    font-size: 11px;
    fill: var(--fg-muted);
  }
  :global(.rp svg .rp-grid) {
    stroke: var(--border);
    stroke-opacity: 0.4;
    stroke-width: 1;
  }
  :global(.rp svg .rp-axisln) {
    stroke: var(--fg-muted);
    stroke-opacity: 0.7;
    stroke-width: 1;
  }
  .rp-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.9rem;
    margin-top: 0.35rem;
    font-size: 0.82em;
    color: var(--fg-muted);
  }
  .rp-legend.compact { gap: 0.15rem 0.55rem; font-size: 0.76em; }
  .rp-key { display: inline-flex; align-items: center; gap: 0.3rem; }
  .rp-swatch {
    width: 0.7rem; height: 0.2rem; border-radius: 1px; display: inline-block;
  }
  .rp-ax { opacity: 0.7; }
  .rp-scale { margin-top: 0.4rem; }
  .rp-scale-btn {
    font-size: 0.78em;
    padding: 0.15rem 0.55rem;
    border-radius: 4px;
  }
</style>

<script lang="ts">
  /**
   * Generic outputs renderer.
   *  - matched-length numeric x/y arrays → inline SVG line plot
   *  - string values that look like .png/.jpg/.svg/.gif filenames →
   *    inline <img> served from /api/jobs/{id}/files/{path}
   *  - string values that look like .csv/.txt/.json/.log filenames →
   *    download link served from the same endpoint
   *  - everything else → pretty-printed JSON (collapsed by default)
   *
   * The file paths in `outputs` are treated as relative to the job's
   * work directory (the runner enforces this server-side; ../ escape
   * attempts return 404).
   */
  let {
    outputs,
    jobId = null
  }: {
    outputs: Record<string, unknown> | null | undefined;
    jobId?: number | null;
  } = $props();

  const IMAGE_EXT = /\.(png|jpe?g|gif|svg|webp)$/i;
  const FILE_EXT  = /\.(csv|tsv|txt|json|log|h5|hdf5|nc|parquet|pq)$/i;

  function looksLikePath(v: unknown): v is string {
    return typeof v === 'string' && (IMAGE_EXT.test(v) || FILE_EXT.test(v));
  }

  function fileUrl(rel: string): string {
    return jobId == null ? '#' : `/api/jobs/${jobId}/files/${rel.replace(/^\/+/, '')}`;
  }

  function categorise(o: Record<string, unknown>) {
    const images: { key: string; path: string }[] = [];
    const files:  { key: string; path: string }[] = [];
    for (const [k, v] of Object.entries(o)) {
      if (typeof v !== 'string') continue;
      if (IMAGE_EXT.test(v)) images.push({ key: k, path: v });
      else if (FILE_EXT.test(v)) files.push({ key: k, path: v });
    }
    return { images, files };
  }

  function isNumberArray(v: unknown): v is number[] {
    return Array.isArray(v) && v.every((x) => typeof x === 'number');
  }

  const cats = $derived(outputs ? categorise(outputs) : { images: [], files: [] });

  const plot = $derived.by(() => {
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
  });

  function humanKey(k: string): string {
    return k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
</script>

{#if outputs}
  {#if plot}
    <div class="plot">
      <svg viewBox="0 0 {plot.W} {plot.H}" width="100%" preserveAspectRatio="xMidYMid meet">
        <rect x="0.5" y="0.5" width={plot.W - 1} height={plot.H - 1}
              fill="none" stroke="var(--border)" />
        {#if plot.ymin < 0 && plot.ymax > 0}
          {@const y0 = plot.H - plot.pad - ((0 - plot.ymin) / (plot.ymax - plot.ymin || 1)) * (plot.H - 2 * plot.pad)}
          <line x1={plot.pad} y1={y0} x2={plot.W - plot.pad} y2={y0}
                stroke="var(--border)" stroke-dasharray="3 3" />
        {/if}
        <path d={plot.d} fill="none" stroke="var(--accent)" stroke-width="2" />
      </svg>
      <p class="muted" style="margin: 0.25rem 0 0; font-size: 0.85em;">
        x ∈ [{plot.xmin.toPrecision(4)}, {plot.xmax.toPrecision(4)}],
        y ∈ [{plot.ymin.toPrecision(4)}, {plot.ymax.toPrecision(4)}]
      </p>
    </div>
  {/if}

  {#if cats.images.length > 0}
    <div class="images">
      {#each cats.images as img}
        <figure class="image-card">
          <a href={fileUrl(img.path)} target="_blank" rel="noopener">
            <img src={fileUrl(img.path)} alt={img.key} loading="lazy" />
          </a>
          <figcaption>{humanKey(img.key)}</figcaption>
        </figure>
      {/each}
    </div>
  {/if}

  {#if cats.files.length > 0}
    <div class="files">
      <h4 class="muted" style="margin: 0.75rem 0 0.25rem; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.04em;">Files</h4>
      <ul>
        {#each cats.files as f}
          <li>
            <a href={fileUrl(f.path)} download>{f.path}</a>
            <span class="muted"> ({humanKey(f.key)})</span>
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  <details>
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
  .images {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 0.75rem;
    margin: 0.5rem 0;
  }
  .image-card {
    margin: 0;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.5rem;
  }
  .image-card img {
    width: 100%;
    height: auto;
    display: block;
    border-radius: 4px;
  }
  .image-card figcaption {
    margin-top: 0.4rem;
    color: var(--fg-muted);
    font-size: 0.85em;
    text-align: center;
  }
  .files ul {
    margin: 0;
    padding-left: 1.25rem;
  }
  .files li { font-family: var(--font-mono); font-size: 0.9em; }
</style>

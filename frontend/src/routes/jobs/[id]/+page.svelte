<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { api, type JobOut, type JsonSchema } from '$lib/api';
  import JobStatus from '$lib/JobStatus.svelte';
  import OutputView from '$lib/OutputView.svelte';

  let job = $state<JobOut | null>(null);
  let outputSchema = $state<JsonSchema | null>(null);
  let logLines = $state<string[]>([]);
  let error = $state('');
  let ws: WebSocket | null = null;
  let cancelling = $state(false);
  type Progress = {
    fraction: number;
    message: string;
    step?: number | null;
    total?: number | null;
    phase?: string | null;
  };
  let progress = $state<Progress | null>(null);
  // Ticks every second so elapsed time is live even when no progress
  // event has arrived yet (so the page never looks frozen).
  let nowMs = $state(Date.now());
  let clock: ReturnType<typeof setInterval> | null = null;

  const jobId = $derived(Number($page.params.id));
  const running = $derived(
    !!job && !['succeeded', 'failed', 'cancelled'].includes(job.status)
  );
  // API timestamps are tz-naive UTC (SQLite drops tzinfo); Date()
  // would read them as local time. Treat a missing offset as UTC so
  // elapsed (vs the live local clock) is correct.
  const tsMs = (s: string): number =>
    Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : s + 'Z');
  const elapsedS = $derived(
    job?.started_at
      ? Math.max(0, (nowMs - tsMs(job.started_at)) / 1000)
      : null
  );

  onMount(async () => {
    try {
      job = await api.getJob(jobId);
      // Best-effort: the code's output schema carries x-output-plots
      // (native result figures). A failure here just falls back to the
      // legacy renderer — never blocks the job view.
      try {
        outputSchema = (await api.getCode(job.code_name)).output_schema;
      } catch { /* code may be unregistered; ignore */ }
      // Backfill any logs that arrived before we connected.
      const logs = await api.jobLogs(jobId);
      logLines = logs.map((row) => row.line);
      // Seed the bar if the job is mid-run when the page loads.
      if (job.progress != null) {
        progress = {
          fraction: job.progress, message: job.progress_message ?? '',
          step: job.progress_step, total: job.progress_total,
          phase: job.progress_phase,
        };
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      return;
    }
    // If the job is still live, subscribe to the stream for incremental updates.
    if (job && !['succeeded', 'failed', 'cancelled'].includes(job.status)) {
      connectWS();
      clock = setInterval(() => { nowMs = Date.now(); }, 1000);
    }
  });

  onDestroy(() => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    if (clock) clearInterval(clock);
  });

  function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/api/jobs/${jobId}/stream`);
    ws.onmessage = async (ev) => {
      const event = JSON.parse(ev.data);
      if (event.type === 'log') {
        logLines = [...logLines, event.line];
      } else if (event.type === 'progress') {
        progress = {
          fraction: event.fraction, message: event.message ?? '',
          step: event.step, total: event.total, phase: event.phase,
        };
      } else if (event.type === 'status') {
        // Refetch the full job to pick up outputs/finished_at/error_text.
        try { job = await api.getJob(jobId); } catch { /* ignore */ }
        if (['succeeded', 'failed', 'cancelled'].includes(event.status)) {
          progress = null;
          if (clock) { clearInterval(clock); clock = null; }
          if (ws) ws.close();
        }
      }
    };
    ws.onerror = () => { /* let onclose handle reconnect-or-give-up; simple: do nothing */ };
  }

  async function cancel() {
    if (!job) return;
    cancelling = true;
    try { await api.cancelJob(job.id); }
    catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { cancelling = false; }
  }

  let deleting = $state(false);
  async function deleteJob() {
    if (!job) return;
    if (!confirm(`Delete job #${job.id} and its on-disk artifacts? This cannot be undone.`)) return;
    deleting = true;
    try {
      await api.cancelJob(job.id);    // same endpoint: cancel-if-live, delete-if-terminal
      goto('/jobs');
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      deleting = false;
    }
  }

  function dur(start: string | null, end: string | null): string {
    if (!start) return '—';
    const s = new Date(start).getTime();
    const e = end ? new Date(end).getTime() : Date.now();
    const ms = e - s;
    if (ms < 1000) return `${ms} ms`;
    return `${(ms / 1000).toFixed(1)} s`;
  }
</script>

<p><a href="/jobs">← my jobs</a></p>

{#if error}
  <p class="danger">{error}</p>
{:else if job === null}
  <p class="muted">Loading…</p>
{:else}
  <div class="row" style="justify-content: space-between; align-items: baseline">
    <h2 style="margin: 0">Job #{job.id} <span class="muted" style="font-weight: 400; font-size: 0.85em">· {job.code_name}</span></h2>
    <JobStatus status={job.status} />
  </div>
  <p class="muted">
    submitted {new Date(job.created_at).toLocaleString()} ·
    duration {dur(job.started_at, job.finished_at)}
    {#if !['succeeded', 'failed', 'cancelled'].includes(job.status)}
      &nbsp;·&nbsp; <button onclick={cancel} disabled={cancelling}>{cancelling ? 'cancelling…' : 'cancel'}</button>
    {:else}
      &nbsp;·&nbsp; <button onclick={deleteJob} disabled={deleting}>{deleting ? 'deleting…' : 'delete'}</button>
    {/if}
  </p>

  {#if running}
    <div class="progress">
      {#if progress}
        <div class="pbar">
          <div class="pfill" style="width: {Math.round(progress.fraction * 100)}%"></div>
        </div>
        <p class="muted pmeta">
          {#if progress.phase}{progress.phase} · {/if}{Math.round(progress.fraction * 100)}%{#if progress.step != null && progress.total != null} · step {progress.step}/{progress.total}{/if}{#if progress.message} · {progress.message}{/if}{#if elapsedS != null} · {elapsedS.toFixed(0)} s elapsed{/if}
        </p>
      {:else}
        <div class="pbar indeterminate"><div class="pfill-i"></div></div>
        <p class="muted pmeta">
          {job.status === 'queued' ? 'queued…' : 'running…'}{#if elapsedS != null} · {elapsedS.toFixed(0)} s elapsed{/if}
        </p>
      {/if}
    </div>
  {/if}

  {#if job.error_text}
    <div class="card danger">
      <strong>Error</strong>
      <pre style="margin: 0.5rem 0 0; white-space: pre-wrap">{job.error_text}</pre>
    </div>
  {/if}

  <h3>Outputs</h3>
  <div class="card">
    <OutputView outputs={job.outputs} jobId={job.id} {outputSchema} />
  </div>

  <h3>Inputs</h3>
  <details>
    <summary class="muted" style="cursor: pointer">show</summary>
    <pre>{JSON.stringify(job.inputs, null, 2)}</pre>
  </details>

  <h3>Log ({logLines.length} lines)</h3>
  <div class="card">
    {#if logLines.length === 0}
      <p class="muted">No log lines.</p>
    {:else}
      <pre style="max-height: 320px; overflow-y: auto; margin: 0">{logLines.join('\n')}</pre>
    {/if}
  </div>
{/if}

<style>
  .progress { margin: 0.25rem 0 0.75rem; }
  .pbar {
    height: 0.55rem;
    border-radius: 999px;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    overflow: hidden;
  }
  .pfill {
    height: 100%;
    background: var(--accent);
    border-radius: 999px;
    transition: width 0.35s ease;
  }
  .pmeta { margin: 0.3rem 0 0; font-size: 0.85em; font-family: var(--font-mono); }
  /* Indeterminate: a sliding sliver until the first real fraction. */
  .pbar.indeterminate { position: relative; }
  .pfill-i {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 35%;
    background: var(--accent);
    border-radius: 999px;
    animation: pslide 1.15s ease-in-out infinite;
  }
  @keyframes pslide {
    0%   { left: -35%; }
    100% { left: 100%; }
  }
</style>

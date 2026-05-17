<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, type JobListItem } from '$lib/api';
  import JobStatus from '$lib/JobStatus.svelte';

  let jobs = $state<JobListItem[] | null>(null);
  let error = $state('');
  let busyId = $state<number | null>(null);

  async function load() {
    try {
      jobs = await api.listJobs({ limit: 100 });
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  onMount(load);

  const terminal = (s: string) =>
    ['succeeded', 'failed', 'cancelled'].includes(s);

  async function remove(job: JobListItem) {
    // Same endpoint as the job page: cancel-if-live, delete-if-terminal.
    const verb = terminal(job.status) ? 'Delete' : 'Cancel';
    if (!confirm(`${verb} job #${job.id}? This cannot be undone.`)) return;
    busyId = job.id;
    try {
      await api.cancelJob(job.id);
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      busyId = null;
    }
  }

  function fmt(ts: string | null) {
    if (!ts) return '—';
    return new Date(ts).toLocaleString();
  }

  // Per-row run details, read from the submitted inputs (ccfly keys;
  // any other code just shows "—").
  function inp(job: JobListItem, key: string): string | null {
    const v = job.inputs?.[key];
    return v == null || v === '' ? null : String(v);
  }
  function spectrumOf(job: JobListItem): string | null {
    const m = inp(job, 'spectrum_mode');
    return m && m !== 'off' ? m : null;
  }

  // Whole-row navigation, except when the click/keypress lands on an
  // interactive child (the delete/cancel button).
  function openJob(ev: Event, job: JobListItem) {
    if ((ev.target as HTMLElement).closest('button, a')) return;
    goto(`/jobs/${job.id}`);
  }
  function rowKey(ev: KeyboardEvent, job: JobListItem) {
    if (ev.key !== 'Enter' && ev.key !== ' ') return;
    if ((ev.target as HTMLElement).closest('button, a')) return;
    ev.preventDefault();
    goto(`/jobs/${job.id}`);
  }
</script>

<div class="page-head">
  <h2>My jobs</h2>
  <button type="button" class="primary" onclick={() => goto('/codes/ccfly')}>
    + New CCFLY run
  </button>
</div>
<p><a href="/">← all codes</a></p>

{#if error}
  <p class="danger">{error}</p>
{:else if jobs === null}
  <p class="muted">Loading…</p>
{:else if jobs.length === 0}
  <p class="muted">
    No jobs yet — <a href="/codes/ccfly">start a CCFLY run</a>.
  </p>
{:else}
  <table>
    <thead>
      <tr>
        <th>Code</th>
        <th>Element</th>
        <th>Mode</th>
        <th>Spectrum</th>
        <th>Submitted</th>
        <th class="col-status">Status</th>
        <th>ID</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each jobs as job}
        <tr
          class="job-row"
          role="link"
          tabindex="0"
          aria-label="Open job {job.id}"
          onclick={(e) => openJob(e, job)}
          onkeydown={(e) => rowKey(e, job)}
        >
          <td>{job.code_name}</td>
          <td>{inp(job, 'species') ?? '—'}</td>
          <td>{inp(job, 'simulation_type') ?? '—'}</td>
          <td>{#if spectrumOf(job)}{spectrumOf(job)}{:else}<span class="muted">—</span>{/if}</td>
          <td class="muted">{fmt(job.created_at)}</td>
          <td class="col-status"><JobStatus dot status={job.status} /></td>
          <td class="muted">#{job.id}</td>
          <td class="actions">
            <button
              type="button"
              onclick={() => remove(job)}
              disabled={busyId === job.id}
            >
              {busyId === job.id
                ? '…'
                : terminal(job.status) ? 'delete' : 'cancel'}
            </button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

<style>
  .page-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }
  .page-head h2 { margin: 0; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }
  th { font-weight: 500; color: var(--fg-muted); font-size: 0.85em; }
  .actions { text-align: right; }
  .actions button { font-size: 0.85em; padding: 0.2rem 0.6rem; }
  tbody .job-row { cursor: pointer; }
  tbody .job-row:hover { background: var(--bg-elev); }
  tbody .job-row:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .col-status { text-align: center; }
</style>

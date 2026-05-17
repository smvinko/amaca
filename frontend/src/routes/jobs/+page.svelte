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
        <th>ID</th>
        <th>Code</th>
        <th>Status</th>
        <th>Submitted</th>
        <th>Finished</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each jobs as job}
        <tr>
          <td><a href="/jobs/{job.id}">#{job.id}</a></td>
          <td>{job.code_name}</td>
          <td><JobStatus status={job.status} /></td>
          <td class="muted">{fmt(job.created_at)}</td>
          <td class="muted">{fmt(job.finished_at)}</td>
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
</style>

<script lang="ts">
  import { onMount } from 'svelte';
  import { api, type JobListItem } from '$lib/api';
  import JobStatus from '$lib/JobStatus.svelte';

  let jobs: JobListItem[] | null = null;
  let error = '';

  async function load() {
    try {
      jobs = await api.listJobs({ limit: 100 });
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  onMount(load);

  function fmt(ts: string | null) {
    if (!ts) return '—';
    return new Date(ts).toLocaleString();
  }
</script>

<h2>My jobs</h2>
<p><a href="/">← all codes</a></p>

{#if error}
  <p class="danger">{error}</p>
{:else if jobs === null}
  <p class="muted">Loading…</p>
{:else if jobs.length === 0}
  <p class="muted">No jobs yet. Submit one from <a href="/">a code page</a>.</p>
{:else}
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>Code</th>
        <th>Status</th>
        <th>Submitted</th>
        <th>Finished</th>
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
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

<style>
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }
  th { font-weight: 500; color: var(--fg-muted); font-size: 0.85em; }
</style>

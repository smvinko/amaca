<script lang="ts">
  import type { JobStatus } from './api';
  // `dot`: render just a colour-coded circle (same status colours as
  // the pill), with the status name as tooltip / accessible label.
  let { status, dot = false }: { status: JobStatus; dot?: boolean } = $props();
</script>

{#if dot}
  <span class="status-dot status-{status}" title={status} aria-label={status}></span>
{:else}
  <span class="status-pill status-{status}">{status}</span>
{/if}

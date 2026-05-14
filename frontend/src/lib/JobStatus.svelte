<script lang="ts">
  import type { JobStatus } from './api';
  export let status: JobStatus;
</script>

<span class="status-pill status-{status}">{status}</span>

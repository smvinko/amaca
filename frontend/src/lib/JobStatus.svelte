<script lang="ts">
  import type { JobStatus } from './api';
  let { status }: { status: JobStatus } = $props();
</script>

<span class="status-pill status-{status}">{status}</span>

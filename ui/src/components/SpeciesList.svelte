<script>
  export let species = [];
  export let sortMode = 'name';
  export let filter = 'all';

  $: filtered = species.filter((sp) => {
    if (filter === 'new') return sp.isNew;
    if (filter === 'recent') return !sp.isNew;
    return true;
  });

  $: sorted = [...filtered].sort((a, b) => {
    if (sortMode === 'name') return a.name.localeCompare(b.name);
    if (sortMode === 'lastSeen') return new Date(b.lastSeen) - new Date(a.lastSeen);
    return 0;
  });
</script>

<ul class="divide-y divide-gray-200 bg-white shadow rounded">
  {#each sorted as sp}
    <li class="p-2 flex justify-between">
      <span>{sp.name}</span>
      <span class="text-sm text-gray-500">{new Date(sp.lastSeen).toLocaleString()}</span>
    </li>
  {/each}
  {#if !sorted.length}
    <li class="p-2 text-center text-gray-500">No species</li>
  {/if}
</ul>

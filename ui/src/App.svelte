<script>
  import SpeciesList from './components/SpeciesList.svelte';

  let sortMode = 'name';
  let filter = 'all';

  // placeholder data; real app will fetch from backend
  let species = [
    { name: 'Blackbird', lastSeen: '2024-05-22T10:00:00', isNew: true },
    { name: 'House Sparrow', lastSeen: '2024-05-22T09:45:00', isNew: false },
    { name: 'Blue Jay', lastSeen: '2024-05-21T16:15:00', isNew: true },
  ];
</script>

<main class="p-4 max-w-3xl mx-auto space-y-4">
  <h1 class="text-2xl font-bold">BirdNET-Pi</h1>

  <div class="flex flex-wrap items-center gap-4">
    <label class="flex items-center gap-1">
      <span>Sort by:</span>
      <select bind:value={sortMode} class="border rounded p-1">
        <option value="name">Name</option>
        <option value="lastSeen">Last Seen</option>
      </select>
    </label>

    <label class="flex items-center gap-1">
      <span>Show:</span>
      <select bind:value={filter} class="border rounded p-1">
        <option value="all">All</option>
        <option value="new">New</option>
        <option value="recent">Recent</option>
      </select>
    </label>
  </div>

  <SpeciesList {species} {sortMode} {filter} />
</main>

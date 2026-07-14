<script setup>
// Скелетон списка вместо спиннера: карточка с N строками-плейсхолдерами.
defineProps({ rows: { type: Number, default: 5 } })
</script>

<template>
  <div class="card" aria-hidden="true">
    <div v-for="i in rows" :key="i" class="sk-row">
      <div class="grow">
        <div class="skeleton" style="height: 15px; width: 62%" />
        <div class="skeleton" style="height: 12px; width: 38%; margin-top: 7px" />
      </div>
      <div class="skeleton" style="height: 30px; width: 76px" />
    </div>
  </div>
</template>

<style scoped>
.sk-row {
  display: flex; align-items: center; gap: var(--s3);
  padding: var(--s3) 0;
  border-bottom: 1px solid var(--border);
}
.sk-row:last-child { border-bottom: none; }
</style>

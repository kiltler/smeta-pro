<script setup>
// Пустое состояние: иконка + одна строка + одно действие.
defineProps({ text: String, action: String })
const emit = defineEmits(['action'])
</script>

<template>
  <div class="empty">
    <div class="empty-circle" aria-hidden="true"><slot name="icon" /></div>
    <p style="margin: 0">{{ text }}</p>
    <button v-if="action" class="soft" @click="emit('action')">{{ action }}</button>
  </div>
</template>

<style scoped>
/* иконка в мягком круге */
.empty-circle {
  width: 76px; height: 76px; border-radius: 50%;
  background: var(--surface-2);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-3);
}
</style>

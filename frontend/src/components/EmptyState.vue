<script setup>
// Пустое состояние: иконка + одна строка + одно действие.
defineProps({ text: String, action: String })
const emit = defineEmits(['action'])
</script>

<template>
  <div class="empty">
    <slot name="icon" />
    <p style="margin: 0">{{ text }}</p>
    <button v-if="action" class="soft" @click="emit('action')">{{ action }}</button>
  </div>
</template>

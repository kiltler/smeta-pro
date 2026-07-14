<script setup>
// Единый вид всех сумм: tabular-nums, неразрывные пробелы, узкий пробел перед ₽.
import { money } from '../composables/ui.js'

defineProps({ value: { type: [Number, String], default: 0 } })
</script>

<template>
  <span class="money">{{ money(value) }}</span>
</template>

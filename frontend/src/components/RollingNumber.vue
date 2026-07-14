<script setup>
// Сумма с «перекатом»: при изменении значения цифры плавно докручиваются
// до нового числа (~400 мс) + микро-пульс масштаба. При reduced-motion — мгновенно.
import { onBeforeUnmount, ref, watch } from 'vue'
import { money, reducedMotion } from '../composables/ui.js'

const props = defineProps({ value: { type: Number, default: 0 } })
const shown = ref(props.value)
const pulsing = ref(false)
let raf = null
let pulseTimer = null

watch(
  () => props.value,
  (to, from) => {
    cancelAnimationFrame(raf)
    if (reducedMotion() || Math.abs(to - from) < 1) {
      shown.value = to
      return
    }
    // микро-пульс: 1 → 1.04 → 1
    pulsing.value = false
    requestAnimationFrame(() => (pulsing.value = true))
    clearTimeout(pulseTimer)
    pulseTimer = setTimeout(() => (pulsing.value = false), 320)

    const start = performance.now()
    const dur = 400
    const step = (now) => {
      const t = Math.min(1, (now - start) / dur)
      const eased = 1 - Math.pow(1 - t, 3) // ease-out cubic
      shown.value = from + (to - from) * eased
      if (t < 1) raf = requestAnimationFrame(step)
      else shown.value = to
    }
    raf = requestAnimationFrame(step)
  }
)
onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  clearTimeout(pulseTimer)
})
</script>

<template>
  <span class="total" :class="{ 'money-pulse': pulsing }" style="display: inline-block">
    {{ money(Math.round(shown)) }}
  </span>
</template>

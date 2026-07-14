// Pull-to-refresh для списков: тянем вниз при scrollY == 0 → refresh().
import { onBeforeUnmount, onMounted, ref } from 'vue'

export function usePullRefresh(refresh) {
  const pulling = ref(false)
  let startY = null

  function onStart(e) {
    if (window.scrollY <= 0) startY = e.touches[0].clientY
  }
  function onMove(e) {
    if (startY === null) return
    const delta = e.touches[0].clientY - startY
    if (delta > 70 && !pulling.value) {
      pulling.value = true
      Promise.resolve(refresh()).finally(() => {
        setTimeout(() => (pulling.value = false), 300)
      })
      startY = null
    }
  }
  function onEnd() {
    startY = null
  }

  onMounted(() => {
    window.addEventListener('touchstart', onStart, { passive: true })
    window.addEventListener('touchmove', onMove, { passive: true })
    window.addEventListener('touchend', onEnd, { passive: true })
  })
  onBeforeUnmount(() => {
    window.removeEventListener('touchstart', onStart)
    window.removeEventListener('touchmove', onMove)
    window.removeEventListener('touchend', onEnd)
  })
  return { pulling }
}

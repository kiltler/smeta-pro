<script setup>
// Нижняя шторка: выезжает снизу с затемнением.
// Закрытие: тап по фону или свайп вниз с инерцией; подложка темнеет
// пропорционально позиции пальца. Пружина возврата — если не докинули.
import { ref } from 'vue'
import { reducedMotion } from '../composables/ui.js'

defineProps({ open: Boolean, title: String })
const emit = defineEmits(['close'])

const sheetEl = ref(null)
const backdropEl = ref(null)

let startY = null
let lastY = 0
let lastT = 0
let velocity = 0
let dragging = false

function onTouchStart(e) {
  if (!sheetEl.value) return
  startY = e.touches[0].clientY
  lastY = startY
  lastT = e.timeStamp
  velocity = 0
  dragging = false
  sheetEl.value.style.transition = 'none'
}

function onTouchMove(e) {
  if (startY === null || !sheetEl.value) return
  const y = e.touches[0].clientY
  const delta = y - startY
  // тянем шторку только вниз и только когда её контент прокручен к верху
  if (delta <= 0 || sheetEl.value.scrollTop > 0) {
    if (!dragging) startY = y // контент скроллится — не начинаем драг
    return
  }
  dragging = true
  velocity = (y - lastY) / Math.max(1, e.timeStamp - lastT)
  lastY = y
  lastT = e.timeStamp
  sheetEl.value.style.transform = `translateY(${delta}px)`
  // подложка темнеет пропорционально позиции пальца
  const progress = Math.min(1, delta / sheetEl.value.offsetHeight)
  if (backdropEl.value) backdropEl.value.style.opacity = String(1 - progress * 0.9)
}

function onTouchEnd() {
  if (!sheetEl.value || !dragging) {
    startY = null
    return
  }
  const delta = lastY - startY
  startY = null
  const height = sheetEl.value.offsetHeight
  // инерция: быстрый бросок или больше 38% высоты — закрываем
  if (velocity > 0.55 || delta > height * 0.38) {
    if (reducedMotion()) {
      resetDrag()
      emit('close')
      return
    }
    sheetEl.value.style.transition = 'transform 200ms ease-in'
    sheetEl.value.style.transform = 'translateY(100%)'
    setTimeout(() => {
      resetDrag()
      emit('close')
    }, 190)
  } else {
    // не докинули — пружина возврата
    sheetEl.value.style.transition = reducedMotion()
      ? 'none'
      : 'transform 320ms cubic-bezier(0.3, 1.35, 0.45, 1)'
    sheetEl.value.style.transform = ''
    if (backdropEl.value) backdropEl.value.style.opacity = ''
  }
}

function resetDrag() {
  if (sheetEl.value) {
    sheetEl.value.style.transition = ''
    sheetEl.value.style.transform = ''
  }
  if (backdropEl.value) backdropEl.value.style.opacity = ''
}
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="open" ref="backdropEl" class="sheet-backdrop" @click.self="emit('close')">
        <div
          ref="sheetEl" class="sheet" role="dialog" aria-modal="true" :aria-label="title"
          @touchstart.passive="onTouchStart"
          @touchmove.passive="onTouchMove"
          @touchend="onTouchEnd"
        >
          <div class="sheet-grip" aria-hidden="true" />
          <div class="sheet-head" v-if="title || $slots.head">
            <slot name="head"><h2 style="margin: 0">{{ title }}</h2></slot>
          </div>
          <div class="sheet-body">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.sheet-backdrop {
  position: fixed; inset: 0; z-index: 60;
  background: var(--backdrop);
  display: flex; align-items: flex-end; justify-content: center;
  transition: opacity 150ms ease;
}
.sheet {
  width: 100%; max-width: 640px;
  max-height: 88dvh;
  overflow-y: auto;
  overscroll-behavior: contain; /* свайп внутри шторки не дёргает страницу */
  -webkit-overflow-scrolling: touch;
  background: var(--surface);
  border-radius: 22px 22px 0 0;
  padding: var(--s2) var(--s4) calc(var(--s5) + env(safe-area-inset-bottom));
  box-shadow: var(--shadow-float);
  touch-action: pan-y;
}
.sheet-grip {
  width: 40px; height: 4px; border-radius: 2px;
  background: var(--border); margin: 6px auto 14px;
}
.sheet-head { margin-bottom: var(--s3); }

/* анимация: фон — fade, шторка — слайд снизу */
.sheet-enter-active, .sheet-leave-active { transition: opacity var(--dur) ease; }
.sheet-enter-active .sheet, .sheet-leave-active .sheet {
  transition: transform 240ms var(--ease);
}
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-from .sheet, .sheet-leave-to .sheet { transform: translateY(100%); }
</style>

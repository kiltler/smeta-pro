<script setup>
// Нижняя шторка: выезжает снизу с затемнением. Закрытие — тап по фону или свайп-кнопка.
defineProps({ open: Boolean, title: String })
const emit = defineEmits(['close'])
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="open" class="sheet-backdrop" @click.self="emit('close')">
        <div class="sheet" role="dialog" aria-modal="true" :aria-label="title">
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
}
.sheet {
  width: 100%; max-width: 640px;
  max-height: 88dvh;
  overflow-y: auto;
  background: var(--surface);
  border-radius: 22px 22px 0 0;
  padding: var(--s2) var(--s4) calc(var(--s5) + env(safe-area-inset-bottom));
  box-shadow: var(--shadow-float);
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

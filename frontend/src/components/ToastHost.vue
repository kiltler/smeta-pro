<script setup>
// Единые тосты успеха/ошибки. Появляются сверху, живут 2.6 c (см. composables/ui.js).
import { CheckCircle2, AlertCircle } from 'lucide-vue-next'
import { toasts } from '../composables/ui.js'
</script>

<template>
  <Teleport to="body">
    <div class="toast-host" aria-live="polite">
      <TransitionGroup name="toast">
        <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">
          <CheckCircle2 v-if="t.type === 'success'" :size="18" />
          <AlertCircle v-else :size="18" />
          <span>{{ t.text }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-host {
  position: fixed; top: calc(10px + env(safe-area-inset-top));
  left: 0; right: 0; z-index: 100;
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  pointer-events: none;
  padding: 0 var(--s4);
}
.toast {
  display: flex; align-items: center; gap: 8px;
  max-width: 480px;
  padding: 11px 16px;
  border-radius: var(--r-s);
  font-size: 14px; font-weight: 600;
  box-shadow: var(--shadow-float);
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
}
.toast.success svg { color: var(--success); }
.toast.error { color: var(--danger); }
.toast.error svg { color: var(--danger); }

.toast-enter-active { transition: all 220ms var(--ease); }
.toast-leave-active { transition: all 180ms ease; }
.toast-enter-from { opacity: 0; transform: translateY(-12px) scale(0.96); }
.toast-leave-to { opacity: 0; transform: translateY(-8px); }
</style>

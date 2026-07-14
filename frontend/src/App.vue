<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { FilePlus2, FileText, Tags, Boxes, UserRound } from 'lucide-vue-next'
import ToastHost from './components/ToastHost.vue'

const route = useRoute()
const showTabs = computed(() => !['/login', '/onboarding'].includes(route.path))

const tabs = [
  { to: '/new', label: 'Смета', icon: FilePlus2 },
  { to: '/docs', label: 'Документы', icon: FileText },
  { to: '/price', label: 'Прайс', icon: Tags },
  { to: '/bundles', label: 'Комплекты', icon: Boxes },
  { to: '/profile', label: 'Профиль', icon: UserRound },
]
const activeIdx = computed(() => tabs.findIndex((t) => t.to === route.path))
</script>

<template>
  <div class="page-wrap">
    <router-view v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" :key="route.path" />
      </Transition>
    </router-view>
  </div>

  <ToastHost />

  <nav v-if="showTabs" class="tabs" aria-label="Основная навигация">
    <!-- pill активного таба: переезжает пружиной между табами -->
    <div
      v-if="activeIdx >= 0" class="nav-pill" aria-hidden="true"
      :style="{ transform: `translateX(${activeIdx * 100}%)` }"
    ><span /></div>
    <router-link v-for="t in tabs" :key="t.to" :to="t.to">
      <component :is="t.icon" :size="22" :stroke-width="1.9" aria-hidden="true" />
      <span>{{ t.label }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.nav-pill {
  position: absolute; top: 5px; left: 0;
  width: 20%; height: 32px;
  display: flex; align-items: center; justify-content: center;
  pointer-events: none;
  transition: transform 340ms cubic-bezier(0.3, 1.35, 0.45, 1); /* пружина */
}
.nav-pill span {
  width: 48px; height: 30px; border-radius: 15px;
  background: var(--nav-pill);
}
@media (prefers-reduced-motion: reduce) {
  .nav-pill { transition: none; }
}
</style>

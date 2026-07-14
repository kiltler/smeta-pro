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
    <router-link v-for="t in tabs" :key="t.to" :to="t.to">
      <component :is="t.icon" :size="22" :stroke-width="1.9" aria-hidden="true" />
      <span>{{ t.label }}</span>
    </router-link>
  </nav>
</template>

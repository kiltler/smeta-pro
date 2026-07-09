<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const showTabs = computed(() => !['/login', '/onboarding'].includes(route.path))
</script>

<template>
  <router-view />
  <nav v-if="showTabs" class="tabs">
    <router-link to="/new">Смета</router-link>
    <router-link to="/price">Прайс</router-link>
    <router-link to="/bundles">Комплекты</router-link>
    <router-link to="/profile">Профиль</router-link>
  </nav>
</template>

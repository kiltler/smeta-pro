<script setup>
// Фирменные мини-иллюстрации в стиле знака: градиентная подложка,
// скруглённые формы, один stroke. Варианты: docs | search | offline.
defineProps({ name: { type: String, required: true } })
</script>

<template>
  <svg width="96" height="96" viewBox="0 0 96 96" aria-hidden="true">
    <defs>
      <linearGradient :id="`ill-g-${name}`" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#3565ec" />
        <stop offset="1" stop-color="#5b54e8" />
      </linearGradient>
    </defs>
    <rect x="8" y="8" width="80" height="80" rx="22" :fill="`url(#ill-g-${name})`" opacity="0.16" />

    <!-- пустые документы -->
    <g v-if="name === 'docs'" fill="none" stroke="var(--accent)" stroke-width="4.5"
       stroke-linecap="round" stroke-linejoin="round">
      <path d="M34 26h20l10 10v32a4 4 0 0 1-4 4H34a4 4 0 0 1-4-4V30a4 4 0 0 1 4-4z" />
      <path d="M54 26v10h10" opacity="0.6" />
      <path d="M38 50h14 M38 60h20" opacity="0.6" />
    </g>

    <!-- поиск без результата -->
    <g v-else-if="name === 'search'" fill="none" stroke="var(--accent)" stroke-width="4.5"
       stroke-linecap="round">
      <circle cx="44" cy="44" r="16" />
      <line x1="56" y1="56" x2="68" y2="68" />
      <path d="M38 44h12" opacity="0.6" />
    </g>

    <!-- офлайн -->
    <g v-else fill="none" stroke="var(--accent)" stroke-width="4.5" stroke-linecap="round">
      <path d="M28 52a20 20 0 0 1 40 0" />
      <path d="M38 60a10 10 0 0 1 20 0" opacity="0.6" />
      <circle cx="48" cy="68" r="3.5" fill="var(--accent)" stroke="none" />
      <line x1="28" y1="28" x2="68" y2="68" stroke="var(--text-2)" />
    </g>
  </svg>
</template>

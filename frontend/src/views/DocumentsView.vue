<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, getToken } from '../api.js'

const route = useRoute()
const docs = ref([])
const error = ref('')
const copiedId = ref(null)
const highlightId = Number(route.query.created) || null

const STATUS = {
  draft: { text: 'Черновик', cls: 'st-draft' },
  sent: { text: 'Просмотрена', cls: 'st-sent' },
  approved: { text: '✓ Согласована', cls: 'st-approved' },
}
const TYPE = { estimate: 'Смета', contract: 'Договор', act: 'Акт' }

const fmt = (n) => Number(n).toLocaleString('ru-RU')
const fmtDate = (iso) => new Date(iso).toLocaleDateString('ru-RU')
const publicUrl = (d) => `${location.origin}/e/${d.public_uuid}`
const isExpired = (d) => d.expires_at && new Date(d.expires_at) < new Date()

async function load() {
  docs.value = await api('/documents')
}
onMounted(load)

async function shareLink(d) {
  const url = publicUrl(d)
  const title = `Смета № ${d.id} — ${fmt(d.total)} ₽`
  if (navigator.share) {
    try {
      await navigator.share({ title, url })
      return
    } catch {} // отменил — предложим копирование
  }
  await navigator.clipboard.writeText(url)
  copiedId.value = d.id
  setTimeout(() => (copiedId.value = null), 2000)
}

async function openPdf(d) {
  // PDF защищён JWT — качаем blob и открываем
  const resp = await fetch(`/api/documents/${d.id}/pdf`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (!resp.ok) {
    error.value = 'Не удалось открыть PDF'
    return
  }
  window.open(URL.createObjectURL(await resp.blob()), '_blank')
}

async function duplicate(d) {
  error.value = ''
  try {
    await api(`/documents/${d.id}/duplicate`, { method: 'POST' })
    await load()
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <h1>Документы</h1>
  <p class="error">{{ error }}</p>

  <p v-if="docs.length === 0" class="muted">
    Пока нет документов. Соберите смету на экране «Смета».
  </p>

  <div
    v-for="d in docs" :key="d.id" class="card"
    :class="{ fresh: d.id === highlightId }"
  >
    <div class="row" style="align-items: baseline">
      <div class="grow">
        <b>{{ TYPE[d.type] }} № {{ d.id }}</b>
        <span class="muted"> от {{ fmtDate(d.created_at) }}</span>
      </div>
      <span :class="['status', STATUS[d.status].cls]">{{ STATUS[d.status].text }}</span>
    </div>
    <div class="muted" style="margin: 6px 0 2px">
      {{ d.client_name || 'Без имени заказчика' }} ·
      <template v-if="isExpired(d)">срок истёк</template>
      <template v-else>до {{ fmtDate(d.expires_at) }}</template>
    </div>
    <div class="total" style="margin: 6px 0 10px">{{ fmt(d.total) }} ₽</div>
    <div class="row">
      <button class="small" :disabled="isExpired(d)" @click="shareLink(d)">
        {{ copiedId === d.id ? '✓ Скопирована' : 'Ссылка клиенту' }}
      </button>
      <button class="small secondary" @click="openPdf(d)">PDF</button>
      <button class="small secondary" @click="duplicate(d)">Дублировать</button>
    </div>
  </div>
</template>

<style scoped>
.status { font-size: 14px; font-weight: 600; padding: 4px 10px; border-radius: 10px; }
.st-draft { background: #eef2f7; color: #6b7a8c; }
.st-sent { background: #fff4e0; color: #a06b00; }
.st-approved { background: #e6f4ea; color: #1b7f3b; }
.fresh { outline: 2px solid var(--blue); }
</style>

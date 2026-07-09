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
  paid: { text: '₽ Оплачена', cls: 'st-paid' },
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

// ---------- договор и акт из согласованной сметы ----------
const hasChildren = (d) => docs.value.some((x) => x.parent_id === d.id)
const canContract = (d) =>
  d.type === 'estimate' && ['approved', 'paid'].includes(d.status) && !hasChildren(d)

const contractForm = ref(null) // {estimateId, type, name, inn, address, phone, deadline}

function openContractForm(d) {
  contractForm.value = {
    estimateId: d.id,
    type: 'person',
    name: d.client_name || '',
    inn: '',
    address: '',
    phone: '',
    deadline: '',
  }
}

const savingContract = ref(false)

async function submitContract() {
  const f = contractForm.value
  error.value = ''
  savingContract.value = true
  try {
    await api(`/documents/${f.estimateId}/contract-act`, {
      method: 'POST',
      body: {
        client: {
          type: f.type,
          name: f.name,
          inn: f.inn.trim() || null,
          address: f.address,
          phone: f.phone,
        },
        work_deadline: f.deadline,
      },
    })
    contractForm.value = null
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    savingContract.value = false
  }
}

// ---------- отметка оплаты + напоминание про чек «Мой налог» ----------
const taxReminder = ref(false)

async function markPaid(d) {
  error.value = ''
  try {
    await api(`/documents/${d.id}/mark-paid`, { method: 'POST' })
    taxReminder.value = true
    await load()
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <h1>Документы</h1>
  <p class="error">{{ error }}</p>

  <!-- Напоминание про чек НПД: штраф за отсутствие чека — 20% суммы -->
  <div v-if="taxReminder" class="card tax-reminder">
    <b>💰 Не забудьте чек в «Мой налог»!</b>
    <p style="margin: 6px 0">
      Оплата получена — сформируйте чек в приложении «Мой налог» и отправьте
      заказчику. За отсутствие чека грозит штраф 20% от суммы.
    </p>
    <button class="small" @click="taxReminder = false">Чек выбит ✓</button>
  </div>

  <!-- Форма заказчика для договора и акта -->
  <div v-if="contractForm" class="card">
    <h2>Договор + акт к смете № {{ contractForm.estimateId }}</h2>
    <div class="row" style="margin-bottom: 4px">
      <button
        class="small" :class="{ secondary: contractForm.type !== 'person' }"
        @click="contractForm.type = 'person'"
      >Физлицо</button>
      <button
        class="small" :class="{ secondary: contractForm.type !== 'company' }"
        @click="contractForm.type = 'company'"
      >Юрлицо / ИП</button>
    </div>
    <label>{{ contractForm.type === 'company' ? 'Название организации' : 'ФИО заказчика' }}</label>
    <input v-model="contractForm.name" :placeholder="contractForm.type === 'company' ? 'ООО «Тёплый дом»' : 'Смирнова Анна Петровна'" />
    <template v-if="contractForm.type === 'company'">
      <label>ИНН организации</label>
      <input v-model="contractForm.inn" inputmode="numeric" placeholder="2721234567" />
    </template>
    <label>Адрес объекта</label>
    <input v-model="contractForm.address" placeholder="г. Хабаровск, ул. Ленина 5, кв. 12" />
    <label>Телефон заказчика</label>
    <input v-model="contractForm.phone" inputmode="tel" placeholder="+7 914 123-45-67" />
    <label>Срок выполнения работ</label>
    <input v-model="contractForm.deadline" placeholder="до 25.07.2026" />
    <div class="row" style="margin-top: 12px">
      <button
        :disabled="savingContract || !contractForm.name || !contractForm.address
                   || !contractForm.phone || !contractForm.deadline"
        @click="submitContract"
      >{{ savingContract ? 'Создаю…' : 'Создать договор и акт' }}</button>
      <button class="secondary" @click="contractForm = null">Отмена</button>
    </div>
  </div>

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
        <span v-if="d.parent_id" class="muted"> · к смете № {{ d.parent_id }}</span>
      </div>
      <span :class="['status', STATUS[d.status].cls]">{{ STATUS[d.status].text }}</span>
    </div>
    <div class="muted" style="margin: 6px 0 2px">
      {{ d.client_name || 'Без имени заказчика' }}
      <template v-if="d.type === 'estimate'">
        · <template v-if="isExpired(d)">срок истёк</template>
        <template v-else>до {{ fmtDate(d.expires_at) }}</template>
      </template>
    </div>
    <div class="total" style="margin: 6px 0 10px">{{ fmt(d.total) }} ₽</div>

    <div v-if="d.type === 'estimate' && d.status === 'paid'" class="muted" style="margin-bottom: 8px">
      💰 Оплачена — не забудьте чек в «Мой налог»
    </div>

    <div class="row" style="flex-wrap: wrap; gap: 8px">
      <template v-if="d.type === 'estimate'">
        <button class="small" :disabled="isExpired(d)" @click="shareLink(d)">
          {{ copiedId === d.id ? '✓ Скопирована' : 'Ссылка клиенту' }}
        </button>
      </template>
      <button class="small secondary" @click="openPdf(d)">PDF</button>
      <template v-if="d.type === 'estimate'">
        <button v-if="canContract(d)" class="small" @click="openContractForm(d)">
          Договор + акт
        </button>
        <button
          v-if="d.status === 'approved'" class="small secondary" @click="markPaid(d)"
        >Оплачено ₽</button>
        <button class="small secondary" @click="duplicate(d)">Дублировать</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.status { font-size: 14px; font-weight: 600; padding: 4px 10px; border-radius: 10px; }
.st-draft { background: #eef2f7; color: #6b7a8c; }
.st-sent { background: #fff4e0; color: #a06b00; }
.st-approved { background: #e6f4ea; color: #1b7f3b; }
.st-paid { background: #1b7f3b; color: #fff; }
.fresh { outline: 2px solid var(--blue); }
.tax-reminder { background: #fff8e1; outline: 2px solid #f0a500; }
</style>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  FileText, Link2, Copy, Check, FileDown, FileSignature,
  Wallet, RefreshCw, Files,
} from 'lucide-vue-next'
import { api, getToken } from '../api.js'
import BottomSheet from '../components/BottomSheet.vue'
import EmptyState from '../components/EmptyState.vue'
import SkeletonList from '../components/SkeletonList.vue'
import { usePullRefresh } from '../composables/pullRefresh.js'
import { haptic, money, toast } from '../composables/ui.js'

const route = useRoute()
const router = useRouter()
const docs = ref([])
const loading = ref(true)
const copiedId = ref(null)
const bumpId = ref(null) // документ, чей статус только что изменился → пружинка бейджа
const highlightId = Number(route.query.created) || null

const STATUS = {
  draft: { text: 'Черновик', cls: 'st-draft' },
  sent: { text: 'Просмотрена', cls: 'st-sent' },
  approved: { text: 'Согласована', cls: 'st-approved' },
  paid: { text: 'Оплачена', cls: 'st-paid' },
}
const TYPE = { estimate: 'Смета', contract: 'Договор', act: 'Акт' }

const fmtDate = (iso) => new Date(iso).toLocaleDateString('ru-RU')
const publicUrl = (d) => `${location.origin}/e/${d.public_uuid}`
const isExpired = (d) => d.expires_at && new Date(d.expires_at) < new Date()

async function load() {
  docs.value = await api('/documents')
  loading.value = false
}
onMounted(load)
const { pulling } = usePullRefresh(load)

async function shareLink(d) {
  const url = publicUrl(d)
  const title = `Смета № ${d.id} — ${money(d.total)}`
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
    toast('Не удалось открыть PDF', 'error')
    return
  }
  window.open(URL.createObjectURL(await resp.blob()), '_blank')
}

async function duplicate(d) {
  try {
    await api(`/documents/${d.id}/duplicate`, { method: 'POST' })
    toast('Смета продублирована')
    await load()
  } catch (e) {
    toast(e.message, 'error')
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
    toast('Договор и акт готовы')
    await load()
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    savingContract.value = false
  }
}

// ---------- отметка оплаты + напоминание про чек «Мой налог» ----------
const taxReminder = ref(false)

async function markPaid(d) {
  try {
    await api(`/documents/${d.id}/mark-paid`, { method: 'POST' })
    haptic()
    taxReminder.value = true
    await load()
    bumpId.value = d.id
    setTimeout(() => (bumpId.value = null), 500)
  } catch (e) {
    toast(e.message, 'error')
  }
}
</script>

<template>
  <div class="screen">
    <h1>Документы</h1>
  
    <div class="ptr" :class="{ active: pulling }" aria-hidden="true"><RefreshCw :size="18" /></div>
  
    <SkeletonList v-if="loading" :rows="4" />
  
    <EmptyState
      v-else-if="docs.length === 0"
      text="Пока нет документов — соберите первую смету"
      action="К смете"
      @action="router.push('/new')"
    >
      <template #icon><Files :size="40" :stroke-width="1.5" /></template>
    </EmptyState>
  
    <div v-else class="stagger">
      <div
        v-for="d in docs" :key="d.id" class="card doc-card"
        :class="{ fresh: d.id === highlightId }"
      >
        <div class="doc-head">
          <div class="grow">
            <b>{{ TYPE[d.type] }} № {{ d.id }}</b>
            <div class="muted">
              {{ fmtDate(d.created_at) }}<template v-if="d.parent_id"> · к смете № {{ d.parent_id }}</template>
            </div>
          </div>
          <span :class="['status', STATUS[d.status].cls, { bump: d.id === bumpId }]">
            {{ STATUS[d.status].text }}
          </span>
        </div>
  
        <div class="doc-meta">
          <span class="grow muted">
            {{ d.client_name || 'Без имени заказчика' }}
            <template v-if="d.type === 'estimate'">
              · <template v-if="isExpired(d)">срок ссылки истёк</template>
              <template v-else>ссылка до {{ fmtDate(d.expires_at) }}</template>
            </template>
          </span>
          <span class="total">{{ money(d.total) }}</span>
        </div>
  
        <div v-if="d.type === 'estimate' && d.status === 'paid'" class="paid-note">
          <Wallet :size="15" aria-hidden="true" /> Оплачена — не забудьте чек в «Мой налог»
        </div>
  
        <div class="doc-actions">
          <button
            v-if="d.type === 'estimate'" class="small soft"
            :disabled="isExpired(d)" @click="shareLink(d)"
          >
            <Check v-if="copiedId === d.id" :size="15" />
            <Link2 v-else :size="15" />
            {{ copiedId === d.id ? 'Скопирована' : 'Ссылка клиенту' }}
          </button>
          <button class="small secondary" @click="openPdf(d)"><FileDown :size="15" /> PDF</button>
          <template v-if="d.type === 'estimate'">
            <button v-if="canContract(d)" class="small soft" @click="openContractForm(d)">
              <FileSignature :size="15" /> Договор + акт
            </button>
            <button v-if="d.status === 'approved'" class="small secondary" @click="markPaid(d)">
              <Wallet :size="15" /> Оплачено
            </button>
            <button class="small secondary" @click="duplicate(d)"><Copy :size="15" /> Дублировать</button>
          </template>
        </div>
      </div>
    </div>
  
    <!-- Шторка: заказчик для договора и акта -->
    <BottomSheet
      :open="Boolean(contractForm)"
      :title="contractForm ? `Договор + акт к смете № ${contractForm.estimateId}` : ''"
      @close="contractForm = null"
    >
      <template v-if="contractForm">
        <div class="segment" role="tablist" aria-label="Тип заказчика">
          <button role="tab" :aria-selected="contractForm.type === 'person'" :class="{ active: contractForm.type === 'person' }" @click="contractForm.type = 'person'">Физлицо</button>
          <button role="tab" :aria-selected="contractForm.type === 'company'" :class="{ active: contractForm.type === 'company' }" @click="contractForm.type = 'company'">Юрлицо / ИП</button>
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
        <button
          class="cta" style="margin-top: 16px"
          :disabled="savingContract || !contractForm.name || !contractForm.address
                     || !contractForm.phone || !contractForm.deadline"
          @click="submitContract"
        >{{ savingContract ? 'Создаю…' : 'Создать договор и акт' }}</button>
      </template>
    </BottomSheet>
  
    <!-- Шторка: напоминание про чек НПД (штраф за отсутствие чека — 20% суммы) -->
    <BottomSheet :open="taxReminder" title="Не забудьте чек в «Мой налог»" @close="taxReminder = false">
      <p class="muted" style="margin: 4px 0 16px">
        Оплата получена — сформируйте чек в приложении «Мой налог» и отправьте
        заказчику. За отсутствие чека грозит штраф 20% от суммы.
      </p>
      <button class="cta" @click="taxReminder = false">Чек выбит</button>
    </BottomSheet>
  </div>
</template>

<style scoped>
.doc-head { display: flex; align-items: flex-start; gap: var(--s3); }
.doc-meta { display: flex; align-items: baseline; gap: var(--s3); margin: var(--s2) 0 var(--s3); }
.paid-note {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: var(--success);
  background: var(--success-bg);
  padding: 8px 12px; border-radius: var(--r-s);
  margin-bottom: var(--s3);
}
.doc-actions { display: flex; flex-wrap: wrap; gap: var(--s2); }
.doc-actions button { display: inline-flex; align-items: center; gap: 6px; }
.fresh { outline: 2px solid var(--accent); outline-offset: -1px; }

.segment {
  display: flex; gap: 4px; padding: 4px;
  background: var(--surface-2); border-radius: var(--r);
  margin-bottom: var(--s2);
}
.segment button {
  min-height: 40px; font-size: 14px; border-radius: 10px;
  background: transparent; color: var(--text-2);
}
.segment button.active { background: var(--surface); color: var(--text); box-shadow: var(--shadow-card); }
</style>

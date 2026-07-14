<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Link2, Copy, Check, FileDown, FileSignature,
  RefreshCw, MoreHorizontal, UserRoundPlus,
} from 'lucide-vue-next'
import { api, getToken } from '../api.js'
import BottomSheet from '../components/BottomSheet.vue'
import EmptyState from '../components/EmptyState.vue'
import Illustration from '../components/Illustration.vue'
import SkeletonList from '../components/SkeletonList.vue'
import Money from '../components/Money.vue'
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

// ---------- два главных действия по статусу, остальное — в меню «⋯» ----------
const menuDoc = ref(null) // документ, для которого открыто меню

function primaryActions(d) {
  if (d.type !== 'estimate') return ['pdf']
  if (d.status === 'approved') {
    return [canContract(d) ? 'contract' : 'link', 'paid']
  }
  if (d.status === 'paid') {
    return [canContract(d) ? 'contract' : 'link', 'pdf']
  }
  return ['link', 'pdf'] // draft | sent
}

function menuActions(d) {
  if (d.type !== 'estimate') return []
  const all = ['link', 'pdf', ...(canContract(d) ? ['contract'] : []), 'duplicate']
  return all.filter((a) => !primaryActions(d).includes(a))
}

function runAction(action, d) {
  menuDoc.value = null
  if (action === 'link') shareLink(d)
  else if (action === 'pdf') openPdf(d)
  else if (action === 'contract') openContractForm(d)
  else if (action === 'duplicate') duplicate(d)
  else if (action === 'paid') markPaid(d)
}

const ACTION_META = {
  link: { label: 'Ссылка клиенту', icon: Link2 },
  pdf: { label: 'PDF', icon: FileDown },
  contract: { label: 'Договор + акт', icon: FileSignature },
  duplicate: { label: 'Дублировать', icon: Copy },
  paid: { label: 'Оплачено', icon: Check },
}

// ---------- имя заказчика: не указано → тихая кнопка «+ имя заказчика» ----------
const nameForm = ref(null) // {docId, value}
const savingName = ref(false)

async function saveClientName() {
  const f = nameForm.value
  if (!f.value.trim()) return
  savingName.value = true
  try {
    await api(`/documents/${f.docId}/client-name`, {
      method: 'PUT',
      body: { client_name: f.value.trim() },
    })
    nameForm.value = null
    toast('Имя заказчика добавлено')
    await load()
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    savingName.value = false
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
      text="Здесь появятся ваши сметы"
      action="Создать первую"
      @action="router.push('/new')"
    >
      <template #icon><Illustration name="docs" /></template>
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
          <div class="doc-name grow">
            <span v-if="d.client_name" class="client-name">{{ d.client_name }}</span>
            <button
              v-else-if="d.type === 'estimate'" class="add-name"
              @click="nameForm = { docId: d.id, value: '' }"
            >
              <UserRoundPlus :size="14" aria-hidden="true" /> имя заказчика
            </button>
            <span v-if="d.type === 'estimate'" class="muted link-note">
              <template v-if="isExpired(d)">срок ссылки истёк</template>
              <template v-else>ссылка до {{ fmtDate(d.expires_at) }}</template>
            </span>
          </div>
          <Money :value="d.total" class="total doc-sum" />
        </div>

        <div v-if="d.type === 'estimate' && d.status === 'paid'" class="paid-note">
          <Check :size="15" aria-hidden="true" /> Оплачена — не забудьте чек в «Мой налог»
        </div>

        <div class="doc-actions">
          <button
            v-for="a in primaryActions(d)" :key="a"
            class="small" :class="a === 'link' || a === 'contract' ? 'soft' : 'secondary'"
            :disabled="a === 'link' && isExpired(d)"
            @click="runAction(a, d)"
          >
            <Check v-if="a === 'link' && copiedId === d.id" :size="15" />
            <component v-else :is="ACTION_META[a].icon" :size="15" />
            {{ a === 'link' && copiedId === d.id ? 'Скопирована' : ACTION_META[a].label }}
          </button>
          <button
            v-if="menuActions(d).length" class="small secondary more-btn"
            aria-label="Ещё действия" @click="menuDoc = d"
          >
            <MoreHorizontal :size="18" />
          </button>
        </div>
      </div>
    </div>

    <!-- Шторка: остальные действия документа -->
    <BottomSheet
      :open="Boolean(menuDoc)"
      :title="menuDoc ? `${TYPE[menuDoc.type]} № ${menuDoc.id}` : ''"
      @close="menuDoc = null"
    >
      <template v-if="menuDoc">
        <button
          v-for="a in menuActions(menuDoc)" :key="a"
          class="menu-item" :disabled="a === 'link' && isExpired(menuDoc)"
          @click="runAction(a, menuDoc)"
        >
          <component :is="ACTION_META[a].icon" :size="18" aria-hidden="true" />
          {{ ACTION_META[a].label }}
        </button>
      </template>
    </BottomSheet>

    <!-- Шторка: имя заказчика задним числом -->
    <BottomSheet :open="Boolean(nameForm)" title="Имя заказчика" @close="nameForm = null">
      <template v-if="nameForm">
        <label>Попадёт в смету и на страницу клиента</label>
        <input
          v-model="nameForm.value" placeholder="Сергей, ул. Ленина 5"
          @keyup.enter="saveClientName"
        />
        <button
          class="cta" style="margin-top: 16px"
          :disabled="savingName || !nameForm.value.trim()" @click="saveClientName"
        >{{ savingName ? 'Сохраняю…' : 'Сохранить' }}</button>
      </template>
    </BottomSheet>

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
.doc-meta { display: flex; align-items: flex-start; gap: var(--s3); margin: var(--s2) 0 var(--s3); }
.doc-name { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.client-name { /* имя — одна строка с многоточием */
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.doc-sum { flex: none; white-space: nowrap; } /* сумма никогда не переносится */
.link-note { font-size: 13px; }

/* тихая кнопка «+ имя заказчика» */
.add-name {
  display: inline-flex; align-items: center; gap: 4px;
  background: none; color: var(--text-3);
  width: auto; min-height: 28px; padding: 2px 6px 2px 0;
  font-size: 13px; font-weight: 500;
}
.add-name:active { color: var(--accent); background: none; transform: none; }

.paid-note {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: var(--success);
  background: var(--success-bg);
  padding: 8px 12px; border-radius: var(--r-s);
  margin-bottom: var(--s3);
}
.doc-actions { display: flex; flex-wrap: wrap; gap: var(--s2); }
.doc-actions button { display: inline-flex; align-items: center; gap: 6px; }
.more-btn { min-width: 44px; padding: 0; justify-content: center; }
.fresh { outline: 2px solid var(--accent); outline-offset: -1px; }

/* пункты меню «⋯» в шторке */
.menu-item {
  display: flex; align-items: center; gap: 12px;
  width: 100%; min-height: var(--touch);
  background: none; color: var(--text);
  font-size: 16px; font-weight: 500; text-align: left;
  border-bottom: 1px solid var(--border);
  border-radius: 0; padding: 0 4px;
}
.menu-item:last-child { border-bottom: none; }
.menu-item:active { background: var(--surface-2); transform: none; }
.menu-item svg { color: var(--text-2); }

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

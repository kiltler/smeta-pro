<script setup>
import { computed, onMounted, ref } from 'vue'
import { Boxes, Plus, RefreshCw, Trash2 } from 'lucide-vue-next'
import { api } from '../api.js'
import BottomSheet from '../components/BottomSheet.vue'
import EmptyState from '../components/EmptyState.vue'
import RollingNumber from '../components/RollingNumber.vue'
import SkeletonList from '../components/SkeletonList.vue'
import Money from '../components/Money.vue'
import { usePullRefresh } from '../composables/pullRefresh.js'
import { money, toast } from '../composables/ui.js'

const bundles = ref([])
const priceItems = ref([])
const loading = ref(true)
// Конструктор: null — скрыт, иначе {id?, name, parts: Map(price_item_id → {qty, ask})}
const editor = ref(null)
const removing = ref(false)

const itemById = computed(() => Object.fromEntries(priceItems.value.map((i) => [i.id, i])))

function bundleSum(items) {
  return items.reduce((sum, p) => {
    const item = itemById.value[p.price_item_id]
    return sum + (item ? Number(item.price) * (p.qty_default ?? p.qty) : 0)
  }, 0)
}

const editorSum = computed(() => {
  if (!editor.value) return 0
  return [...editor.value.parts.entries()].reduce(
    (sum, [id, p]) => sum + Number(itemById.value[id]?.price || 0) * p.qty, 0
  )
})

async function load() {
  ;[bundles.value, priceItems.value] = await Promise.all([api('/bundles'), api('/pricelist')])
  loading.value = false
}
onMounted(load)
const { pulling } = usePullRefresh(load)

function newBundle() {
  editor.value = { id: null, name: '', parts: new Map() }
}

function editBundle(bundle) {
  editor.value = {
    id: bundle.id,
    name: bundle.name,
    parts: new Map(bundle.items.map((p) => [p.price_item_id, { qty: p.qty_default, ask: p.ask_qty }])),
  }
}

function inc(itemId, delta) {
  const parts = editor.value.parts
  const current = parts.get(itemId)
  const qty = (current?.qty || 0) + delta
  if (qty <= 0) parts.delete(itemId)
  else parts.set(itemId, { qty, ask: current?.ask || false })
}

function toggleAsk(itemId) {
  const p = editor.value.parts.get(itemId)
  if (p) editor.value.parts.set(itemId, { ...p, ask: !p.ask })
}

async function saveBundle() {
  const body = {
    name: editor.value.name,
    items: [...editor.value.parts.entries()].map(([id, p]) => ({
      price_item_id: id,
      qty_default: p.qty,
      ask_qty: p.ask,
    })),
  }
  try {
    if (editor.value.id) await api(`/bundles/${editor.value.id}`, { method: 'PUT', body })
    else await api('/bundles', { method: 'POST', body })
    editor.value = null
    toast('Комплект сохранён')
    await load()
  } catch (e) {
    toast(e.message, 'error')
  }
}

async function removeBundle() {
  if (!removing.value) {
    removing.value = true // первый тап — подтверждение прямо на кнопке
    setTimeout(() => (removing.value = false), 3000)
    return
  }
  try {
    await api(`/bundles/${editor.value.id}`, { method: 'DELETE' })
    editor.value = null
    removing.value = false
    toast('Комплект удалён')
    await load()
  } catch (e) {
    toast(e.message, 'error')
  }
}

function partsPreview(bundle) {
  return bundle.items
    .map((p) => {
      const i = itemById.value[p.price_item_id]
      return i ? `${i.name} ×${p.qty_default}${p.ask_qty ? '?' : ''}` : '?'
    })
    .join(', ')
}
</script>

<template>
  <div class="screen">
    <h1>Комплекты</h1>
  
    <div class="ptr" :class="{ active: pulling }" aria-hidden="true"><RefreshCw :size="18" /></div>
  
    <button class="soft" style="margin-bottom: 12px" @click="newBundle">
      <Plus :size="17" style="margin-right: 6px" /> Новый комплект
    </button>
  
    <SkeletonList v-if="loading" :rows="4" />
  
    <EmptyState
      v-else-if="bundles.length === 0"
      text="Соберите типовые монтажи в комплекты — смета за два тапа"
      action="Создать комплект"
      @action="newBundle"
    >
      <template #icon><Boxes :size="40" :stroke-width="1.5" /></template>
    </EmptyState>
  
    <div v-else class="card dense">
      <button
        v-for="bundle in bundles" :key="bundle.id"
        class="list-item row-btn" @click="editBundle(bundle)"
      >
        <span class="grow">
          <span class="item-name">{{ bundle.name }}</span>
          <span class="muted item-sub">{{ bundle.items.length }} поз. · {{ partsPreview(bundle) }}</span>
        </span>
        <Money :value="bundleSum(bundle.items)" />
      </button>
    </div>
  
    <!-- Шторка: конструктор комплекта -->
    <BottomSheet
      :open="Boolean(editor)"
      :title="editor?.id ? 'Правка комплекта' : 'Новый комплект'"
      @close="editor = null; removing = false"
    >
      <template v-if="editor">
        <label>Название</label>
        <input v-model="editor.name" placeholder="Стандартный монтаж 09" />
  
        <label style="margin-top: 14px">Состав — жмите −/+ у позиций</label>
        <div class="dense">
          <div v-for="item in priceItems" :key="item.id" class="list-item">
            <div class="grow">
              <div>{{ item.name }}</div>
              <div class="muted" style="font-size: 13px"><Money :value="item.price" style="font-weight: 600" /> / {{ item.unit }}</div>
              <label v-if="editor.parts.has(item.id)" class="ask-row">
                <input
                  type="checkbox"
                  :checked="editor.parts.get(item.id).ask"
                  @change="toggleAsk(item.id)"
                />
                <span class="muted">спрашивать количество</span>
              </label>
            </div>
            <div class="stepper">
              <button type="button" :aria-label="`Убрать ${item.name}`" @click="inc(item.id, -1)">−</button>
              <span class="qty">{{ editor.parts.get(item.id)?.qty || 0 }}</span>
              <button type="button" :aria-label="`Добавить ${item.name}`" @click="inc(item.id, 1)">+</button>
            </div>
          </div>
        </div>
  
        <div class="row" style="margin: 14px 0 4px; align-items: baseline">
          <span class="muted">Итого</span>
          <RollingNumber :value="editorSum" style="text-align: right" />
        </div>
        <button
          class="cta" style="margin-top: 10px"
          :disabled="!editor.name || editor.parts.size === 0" @click="saveBundle"
        >Сохранить</button>
        <button v-if="editor.id" class="danger" style="margin-top: 8px" @click="removeBundle">
          <Trash2 :size="16" style="margin-right: 6px" />
          {{ removing ? 'Точно удалить комплект?' : 'Удалить комплект' }}
        </button>
      </template>
    </BottomSheet>
  </div>
</template>

<style scoped>
button.soft { display: flex; align-items: center; justify-content: center; }
button.danger { display: flex; align-items: center; justify-content: center; }

.row-btn {
  width: 100%; background: none; color: var(--text);
  border-radius: 0; padding-left: 0; padding-right: 0;
  font-weight: 400; font-size: 16px; text-align: left;
}
.row-btn:active { background: var(--surface-2); transform: none; }
.row-btn .grow { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.item-name { line-height: 1.3; font-weight: 600; }
.item-sub {
  font-size: 13px; overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}

.ask-row { display: flex; align-items: center; gap: 8px; margin: 6px 0 0; }
.ask-row input[type="checkbox"] {
  width: 22px; height: 22px; min-height: 0; flex: none; accent-color: var(--accent);
}
.ask-row .muted { margin: 0; }
</style>

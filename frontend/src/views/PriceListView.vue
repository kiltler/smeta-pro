<script setup>
import { computed, onMounted, ref } from 'vue'
import { Pencil, Plus, Search, Tags, RefreshCw } from 'lucide-vue-next'
import { api } from '../api.js'
import BottomSheet from '../components/BottomSheet.vue'
import EmptyState from '../components/EmptyState.vue'
import SkeletonList from '../components/SkeletonList.vue'
import Money from '../components/Money.vue'
import { usePullRefresh } from '../composables/pullRefresh.js'
import { money, toast } from '../composables/ui.js'

const items = ref([])
const loading = ref(true)
const search = ref('')
// Редактор в шторке: null — скрыт; {id: null,…} — новая позиция
const editor = ref(null)
const removing = ref(false)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return items.value
  return items.value.filter(
    (i) =>
      i.name.toLowerCase().includes(q) ||
      (i.synonyms || []).some((s) => s.toLowerCase().includes(q))
  )
})

async function load() {
  items.value = await api('/pricelist')
  loading.value = false
}
onMounted(load)
const { pulling } = usePullRefresh(load)

function openNew() {
  editor.value = { id: null, name: '', unit: 'шт', price: '' }
}

function openEdit(item) {
  editor.value = { id: item.id, name: item.name, unit: item.unit, price: item.price }
}

async function saveEditor() {
  const e = editor.value
  const body = { name: e.name, unit: e.unit, price: String(e.price) }
  try {
    if (e.id) await api(`/pricelist/${e.id}`, { method: 'PUT', body })
    else await api('/pricelist', { method: 'POST', body })
    editor.value = null
    toast('Сохранено')
    await load()
  } catch (err) {
    toast(err.message, 'error')
  }
}

async function removeItem() {
  const e = editor.value
  if (!removing.value) {
    removing.value = true // первый тап — подтверждение прямо на кнопке
    setTimeout(() => (removing.value = false), 3000)
    return
  }
  try {
    await api(`/pricelist/${e.id}`, { method: 'DELETE' })
    editor.value = null
    removing.value = false
    toast('Позиция удалена')
    await load()
  } catch (err) {
    toast(err.message, 'error')
  }
}
</script>

<template>
  <div class="screen">
    <h1>Прайс</h1>
  
    <div class="ptr" :class="{ active: pulling }" aria-hidden="true"><RefreshCw :size="18" /></div>
  
    <div class="search-wrap">
      <Search :size="18" class="search-icon" aria-hidden="true" />
      <input v-model="search" type="search" placeholder="Поиск по прайсу…" aria-label="Поиск по прайсу" />
    </div>
  
    <button class="soft" style="margin-bottom: 12px" @click="openNew">
      <Plus :size="17" style="margin-right: 6px" /> Добавить позицию
    </button>
  
    <SkeletonList v-if="loading" :rows="8" />
  
    <EmptyState
      v-else-if="filtered.length === 0 && !search"
      text="Прайс пуст — добавьте первую позицию"
      action="Добавить"
      @action="openNew"
    >
      <template #icon><Tags :size="40" :stroke-width="1.5" /></template>
    </EmptyState>
  
    <div v-else class="card dense">
      <p v-if="filtered.length === 0" class="muted" style="text-align: center; padding: 10px 0">
        По запросу «{{ search }}» ничего нет
      </p>
      <button
        v-for="item in filtered" :key="item.id"
        class="list-item row-btn" @click="openEdit(item)"
      >
        <span class="grow">
          <span class="item-name">{{ item.name }}</span>
          <span class="muted item-sub"><Money :value="item.price" style="font-weight: 600" /> / {{ item.unit }}</span>
        </span>
        <Pencil :size="16" class="edit-ic" aria-hidden="true" />
      </button>
    </div>
  
    <!-- Шторка: добавление/правка позиции -->
    <BottomSheet
      :open="Boolean(editor)"
      :title="editor?.id ? 'Правка позиции' : 'Новая позиция'"
      @close="editor = null; removing = false"
    >
      <template v-if="editor">
        <label>Название</label>
        <input v-model="editor.name" placeholder="Монтаж сплит-системы 24" />
        <div class="row" style="margin-top: 4px">
          <div>
            <label>Единица</label>
            <input v-model="editor.unit" placeholder="шт / м / компл" />
          </div>
          <div>
            <label>Цена, ₽</label>
            <input v-model="editor.price" inputmode="decimal" />
          </div>
        </div>
        <button
          class="cta" style="margin-top: 16px"
          :disabled="!editor.name || !editor.price" @click="saveEditor"
        >Сохранить</button>
        <button v-if="editor.id" class="danger" style="margin-top: 8px" @click="removeItem">
          {{ removing ? 'Точно удалить? Пропадёт и из комплектов' : 'Удалить позицию' }}
        </button>
      </template>
    </BottomSheet>
  </div>
</template>

<style scoped>
.search-wrap { position: relative; margin-bottom: var(--s3); }
.search-wrap .search-icon {
  position: absolute; left: 14px; top: 50%; transform: translateY(-50%);
  color: var(--text-3); pointer-events: none;
}
.search-wrap input { padding-left: 42px; border-radius: var(--r); }

button.soft { display: flex; align-items: center; justify-content: center; }

/* строка прайса как кнопка: вся строка — тач-таргет */
.row-btn {
  width: 100%; background: none; color: var(--text);
  border-radius: 0; padding-left: 0; padding-right: 0;
  font-weight: 400; font-size: 16px; text-align: left;
}
.row-btn:active { background: var(--surface-2); transform: none; }
.row-btn .grow { display: flex; flex-direction: column; gap: 2px; }
.item-name { line-height: 1.3; }
.item-sub { font-size: 13px; }
.edit-ic { color: var(--text-3); flex: none; }
</style>

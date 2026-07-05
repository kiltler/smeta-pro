<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'

const items = ref([])
const search = ref('')
const error = ref('')
const editingId = ref(null)
const showAdd = ref(false)
const draft = ref({ name: '', unit: 'шт', price: '' })

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
}
onMounted(load)

async function saveItem(item) {
  error.value = ''
  try {
    await api(`/pricelist/${item.id}`, {
      method: 'PUT',
      body: { name: item.name, unit: item.unit, price: String(item.price) },
    })
    editingId.value = null
  } catch (e) {
    error.value = e.message
  }
}

async function removeItem(item) {
  if (!confirm(`Удалить «${item.name}»? Позиция пропадёт и из комплектов.`)) return
  error.value = ''
  try {
    await api(`/pricelist/${item.id}`, { method: 'DELETE' })
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function addItem() {
  error.value = ''
  try {
    await api('/pricelist', {
      method: 'POST',
      body: { name: draft.value.name, unit: draft.value.unit, price: String(draft.value.price) },
    })
    draft.value = { name: '', unit: 'шт', price: '' }
    showAdd.value = false
    await load()
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <h1>Прайс</h1>

  <input v-model="search" type="search" placeholder="Поиск по прайсу…" />
  <p class="error">{{ error }}</p>

  <button v-if="!showAdd" style="margin-bottom: 12px" @click="showAdd = true">
    + Добавить позицию
  </button>
  <div v-else class="card">
    <label>Название</label>
    <input v-model="draft.name" placeholder="Монтаж сплит-системы 24" />
    <div class="row" style="margin-top: 10px">
      <div>
        <label>Единица</label>
        <input v-model="draft.unit" placeholder="шт / м / компл" />
      </div>
      <div>
        <label>Цена, ₽</label>
        <input v-model="draft.price" inputmode="numeric" />
      </div>
    </div>
    <div class="row" style="margin-top: 12px">
      <button :disabled="!draft.name || !draft.price" @click="addItem">Сохранить</button>
      <button class="secondary" @click="showAdd = false">Отмена</button>
    </div>
  </div>

  <div class="card">
    <p v-if="filtered.length === 0" class="muted">Ничего не найдено</p>
    <div v-for="item in filtered" :key="item.id" class="list-item">
      <template v-if="editingId === item.id">
        <div class="grow">
          <input v-model="item.name" />
          <div class="row" style="margin-top: 8px">
            <input v-model="item.unit" />
            <input v-model="item.price" inputmode="numeric" class="price-input" />
          </div>
          <div class="row" style="margin-top: 8px">
            <button class="small" @click="saveItem(item)">Сохранить</button>
            <button class="small danger" @click="removeItem(item)">Удалить</button>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="grow" @click="editingId = item.id">
          <div>{{ item.name }}</div>
          <div class="muted">{{ Number(item.price).toLocaleString('ru-RU') }} ₽ / {{ item.unit }}</div>
        </div>
        <button class="small secondary" @click="editingId = item.id">✎</button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'

const bundles = ref([])
const priceItems = ref([])
const error = ref('')
// Конструктор: null — скрыт, иначе {id?, name, parts: Map(price_item_id → {qty, ask})}
const editor = ref(null)

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
}
onMounted(load)

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
  error.value = ''
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
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function removeBundle(bundle) {
  if (!confirm(`Удалить комплект «${bundle.name}»?`)) return
  await api(`/bundles/${bundle.id}`, { method: 'DELETE' })
  await load()
}

const fmt = (n) => n.toLocaleString('ru-RU')
</script>

<template>
  <h1>Комплекты</h1>
  <p class="error">{{ error }}</p>

  <!-- Конструктор -->
  <div v-if="editor" class="card">
    <h2>{{ editor.id ? 'Правка комплекта' : 'Новый комплект' }}</h2>
    <label>Название</label>
    <input v-model="editor.name" placeholder="Стандартный монтаж 09" />

    <label style="margin-top: 14px">Состав — жмите −/+ у позиций</label>
    <div v-for="item in priceItems" :key="item.id" class="list-item">
      <div class="grow">
        <div>{{ item.name }}</div>
        <div class="muted">{{ fmt(Number(item.price)) }} ₽ / {{ item.unit }}</div>
        <label v-if="editor.parts.has(item.id)" class="row" style="margin-top: 6px; align-items: center">
          <input
            type="checkbox" style="min-height: 28px; width: 28px; flex: none"
            :checked="editor.parts.get(item.id).ask"
            @change="toggleAsk(item.id)"
          />
          <span class="muted" style="flex: 1">спрашивать количество</span>
        </label>
      </div>
      <div class="stepper">
        <button type="button" @click="inc(item.id, -1)">−</button>
        <span class="qty">{{ editor.parts.get(item.id)?.qty || 0 }}</span>
        <button type="button" @click="inc(item.id, 1)">+</button>
      </div>
    </div>

    <p class="total" style="margin: 14px 0">Итого: {{ fmt(editorSum) }} ₽</p>
    <div class="row">
      <button :disabled="!editor.name || editor.parts.size === 0" @click="saveBundle">
        Сохранить
      </button>
      <button class="secondary" @click="editor = null">Отмена</button>
    </div>
  </div>

  <!-- Список -->
  <template v-else>
    <button style="margin-bottom: 12px" @click="newBundle">+ Новый комплект</button>
    <div class="card">
      <p v-if="bundles.length === 0" class="muted">Пока нет комплектов</p>
      <div v-for="bundle in bundles" :key="bundle.id" class="list-item">
        <div class="grow" @click="editBundle(bundle)">
          <div>{{ bundle.name }}</div>
          <div class="muted">
            {{ bundle.items.length }} поз. ·
            {{ bundle.items.map((p) => {
              const i = itemById[p.price_item_id]
              return i ? `${i.name} ×${p.qty_default}${p.ask_qty ? '?' : ''}` : '?'
            }).join(', ') }}
          </div>
        </div>
        <div style="text-align: right">
          <div class="total">{{ fmt(bundleSum(bundle.items)) }} ₽</div>
          <button class="small danger" style="margin-top: 6px" @click="removeBundle(bundle)">
            Удалить
          </button>
        </div>
      </div>
    </div>
  </template>
</template>

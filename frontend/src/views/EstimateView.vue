<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'

// ---------- данные ----------
const priceItems = ref([])
const bundles = ref([])
const error = ref('')
const tab = ref('templates') // templates | voice | text

const itemById = computed(() => Object.fromEntries(priceItems.value.map((i) => [i.id, i])))
const fmt = (n) => Number(n).toLocaleString('ru-RU')

onMounted(async () => {
  ;[priceItems.value, bundles.value] = await Promise.all([api('/pricelist'), api('/bundles')])
})

// ---------- корзина сметы (живёт в localStorage до создания документа) ----------
const CART_KEY = 'smeta_cart'
const cart = ref(JSON.parse(localStorage.getItem(CART_KEY) || '[]'))

function saveCart() {
  localStorage.setItem(CART_KEY, JSON.stringify(cart.value))
}

function addToCart(item, qty) {
  const existing = cart.value.find((p) => p.price_item_id === item.price_item_id)
  if (existing) existing.qty = Math.round((existing.qty + qty) * 100) / 100
  else cart.value.push({ ...item, qty })
  cart.value = cart.value.filter((p) => p.qty > 0)
  saveCart()
}

function addPriceItem(item, qty = 1) {
  addToCart(
    { price_item_id: item.id, name: item.name, unit: item.unit, price: item.price },
    qty
  )
}

const cartTotal = computed(() =>
  cart.value.reduce((sum, p) => sum + Number(p.price) * p.qty, 0)
)
const cartQty = (id) => cart.value.find((p) => p.price_item_id === id)?.qty || 0

function clearCart() {
  if (!confirm('Очистить смету?')) return
  cart.value = []
  saveCart()
}

// ---------- шаблоны: сортировка комплектов по частоте использования ----------
const USAGE_KEY = 'smeta_bundle_usage'
const usage = ref(JSON.parse(localStorage.getItem(USAGE_KEY) || '{}'))

const sortedBundles = computed(() =>
  [...bundles.value].sort(
    (a, b) => (usage.value[b.id] || 0) - (usage.value[a.id] || 0) || a.sort - b.sort
  )
)

function bundleSum(bundle) {
  return bundle.items.reduce(
    (sum, p) => sum + Number(itemById.value[p.price_item_id]?.price || 0) * p.qty_default, 0
  )
}

// мини-диалог «сколько метров?» для ask_qty-позиций комплекта
const askDialog = ref(null) // {bundle, parts: [{part, item, qty}]}

function tapBundle(bundle) {
  usage.value[bundle.id] = (usage.value[bundle.id] || 0) + 1
  localStorage.setItem(USAGE_KEY, JSON.stringify(usage.value))

  const askParts = bundle.items.filter((p) => p.ask_qty)
  if (askParts.length === 0) return applyBundle(bundle, {})
  askDialog.value = {
    bundle,
    parts: askParts.map((part) => ({
      part,
      item: itemById.value[part.price_item_id],
      qty: part.qty_default,
    })),
  }
}

function applyBundle(bundle, askedQty) {
  for (const part of bundle.items) {
    const item = itemById.value[part.price_item_id]
    if (!item) continue
    addPriceItem(item, askedQty[part.price_item_id] ?? part.qty_default)
  }
  askDialog.value = null
}

function confirmAskDialog() {
  const asked = Object.fromEntries(
    askDialog.value.parts.map(({ part, qty }) => [part.price_item_id, Number(qty) || 0])
  )
  applyBundle(askDialog.value.bundle, asked)
}

// ---------- голос (Web Speech API, ru-RU) + текст ----------
const SR = window.SpeechRecognition || window.webkitSpeechRecognition
const voiceSupported = Boolean(SR)
const listening = ref(false)
const dictation = ref('')
let recognition = null

function toggleVoice() {
  if (listening.value) {
    recognition?.stop()
    return
  }
  recognition = new SR()
  recognition.lang = 'ru-RU'
  recognition.interimResults = true
  recognition.continuous = true
  let finalText = dictation.value ? dictation.value + ' ' : ''
  recognition.onresult = (event) => {
    let interim = ''
    for (const result of event.results) {
      if (result.isFinal) {
        finalText += result[0].transcript + ' '
        interim = ''
      } else interim += result[0].transcript
    }
    dictation.value = (finalText + interim).trim()
  }
  recognition.onend = () => (listening.value = false)
  recognition.onerror = () => (listening.value = false)
  recognition.start()
  listening.value = true
}

// ---------- /parse + экран проверки ----------
const parsing = ref(false)
const review = ref(null) // {parse_log_id, positions:[...], unrecognized:[...]}

async function runParse() {
  if (!dictation.value.trim()) return
  error.value = ''
  parsing.value = true
  try {
    review.value = await api('/parse', { method: 'POST', body: { text: dictation.value } })
  } catch (e) {
    error.value = e.message
  } finally {
    parsing.value = false
  }
}

function removeReviewPosition(index) {
  review.value.positions.splice(index, 1)
}

async function confirmReview() {
  // фиксируем правку (материал для улучшения промпта), затем — в корзину
  const positions = review.value.positions
    .map((p) => ({ ...p, qty: Number(p.qty) || 0 }))
    .filter((p) => p.qty > 0)
  try {
    await api(`/parse/${review.value.parse_log_id}`, {
      method: 'PUT',
      body: { positions },
    })
  } catch {
    // правка — телеметрия; не блокируем пользователя, если она не записалась
  }
  for (const p of positions) {
    addToCart(
      { price_item_id: p.price_item_id, name: p.name, unit: p.unit, price: p.price },
      p.qty
    )
  }
  review.value = null
  dictation.value = ''
  tab.value = 'templates'
}
</script>

<template>
  <h1>Новая смета</h1>
  <p class="error">{{ error }}</p>

  <!-- Экран проверки распознанного (обязателен перед добавлением) -->
  <div v-if="review" class="card">
    <h2>Проверьте распознанное</h2>
    <p class="muted">Поправьте количество или удалите лишнее — потом «В смету».</p>
    <div v-for="(p, i) in review.positions" :key="p.price_item_id" class="list-item">
      <div class="grow">
        <div>{{ p.name }}</div>
        <div class="muted">{{ fmt(p.price) }} ₽ / {{ p.unit }}</div>
      </div>
      <input v-model="p.qty" class="price-input" inputmode="decimal" style="max-width: 90px" />
      <button class="small danger" @click="removeReviewPosition(i)">✕</button>
    </div>
    <p v-if="review.unrecognized.length" class="muted">
      Не распознано: {{ review.unrecognized.join(', ') }} — добавьте вручную из «Шаблонов».
    </p>
    <div class="row" style="margin-top: 12px">
      <button :disabled="review.positions.length === 0" @click="confirmReview">В смету</button>
      <button class="secondary" @click="review = null">Отмена</button>
    </div>
  </div>

  <!-- Мини-диалог «сколько метров?» -->
  <div v-else-if="askDialog" class="card">
    <h2>{{ askDialog.bundle.name }}</h2>
    <div v-for="entry in askDialog.parts" :key="entry.part.price_item_id">
      <label>{{ entry.item?.name }} — сколько {{ entry.item?.unit }}?</label>
      <input v-model="entry.qty" inputmode="decimal" />
    </div>
    <div class="row" style="margin-top: 12px">
      <button @click="confirmAskDialog">Добавить</button>
      <button class="secondary" @click="askDialog = null">Отмена</button>
    </div>
  </div>

  <template v-else>
    <!-- Табы режимов ввода -->
    <div class="mode-tabs">
      <button :class="{ active: tab === 'templates' }" @click="tab = 'templates'">Шаблоны</button>
      <button :class="{ active: tab === 'voice' }" @click="tab = 'voice'">Голос</button>
      <button :class="{ active: tab === 'text' }" @click="tab = 'text'">Текст</button>
    </div>

    <!-- ШАБЛОНЫ -->
    <template v-if="tab === 'templates'">
      <div class="bundle-grid">
        <button
          v-for="bundle in sortedBundles" :key="bundle.id"
          class="bundle-btn" @click="tapBundle(bundle)"
        >
          <span>{{ bundle.name }}</span>
          <span class="bundle-price">{{ fmt(bundleSum(bundle)) }} ₽</span>
        </button>
      </div>

      <div class="card">
        <div v-for="item in priceItems" :key="item.id" class="list-item">
          <div class="grow">
            <div>{{ item.name }}</div>
            <div class="muted">{{ fmt(item.price) }} ₽ / {{ item.unit }}</div>
          </div>
          <div class="stepper">
            <button type="button" @click="addPriceItem(item, -1)">−</button>
            <span class="qty">{{ cartQty(item.id) }}</span>
            <button type="button" @click="addPriceItem(item, 1)">+</button>
          </div>
        </div>
      </div>
    </template>

    <!-- ГОЛОС -->
    <div v-else-if="tab === 'voice'" class="card">
      <template v-if="voiceSupported">
        <button :class="{ danger: listening }" @click="toggleVoice">
          {{ listening ? '■ Стоп' : '🎤 Говорите' }}
        </button>
        <label style="margin-top: 12px">Распознанный текст (можно поправить)</label>
      </template>
      <p v-else class="muted">
        Голосовой ввод не поддерживается этим браузером — введите текст вручную.
      </p>
      <textarea
        v-model="dictation"
        placeholder="монтаж девятки, трасса 4 метра, штроба бетон 2 метра, помпа"
      />
      <button style="margin-top: 12px" :disabled="parsing || !dictation.trim()" @click="runParse">
        {{ parsing ? 'Распознаю…' : 'Распознать позиции' }}
      </button>
    </div>

    <!-- ТЕКСТ -->
    <div v-else class="card">
      <label>Опишите работы своими словами</label>
      <textarea
        v-model="dictation"
        placeholder="монтаж девятки, трасса 4 метра, штроба бетон 2 метра, помпа"
      />
      <button style="margin-top: 12px" :disabled="parsing || !dictation.trim()" @click="runParse">
        {{ parsing ? 'Распознаю…' : 'Распознать позиции' }}
      </button>
    </div>

    <!-- Корзина сметы: всегда видна -->
    <div class="card cart">
      <h2>Смета</h2>
      <p v-if="cart.length === 0" class="muted">Пока пусто — добавьте комплект или позиции</p>
      <div v-for="p in cart" :key="p.price_item_id" class="list-item">
        <div class="grow">
          <div>{{ p.name }}</div>
          <div class="muted">{{ fmt(p.price) }} ₽ × {{ p.qty }} {{ p.unit }}</div>
        </div>
        <div class="stepper">
          <button type="button" @click="addToCart(p, -1)">−</button>
          <span class="qty">{{ p.qty }}</span>
          <button type="button" @click="addToCart(p, 1)">+</button>
        </div>
      </div>
      <div v-if="cart.length" class="row" style="margin-top: 12px; align-items: center">
        <span class="total grow">Итого: {{ fmt(cartTotal) }} ₽</span>
        <button class="small secondary" @click="clearCart">Очистить</button>
      </div>
      <p v-if="cart.length" class="muted" style="margin-top: 8px">
        PDF-смета и отправка клиенту появятся в следующем обновлении.
      </p>
    </div>
  </template>
</template>

<style scoped>
.mode-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}
.mode-tabs button {
  min-height: 48px;
  background: #e6ecf5;
  color: var(--blue);
}
.mode-tabs button.active {
  background: var(--blue);
  color: #fff;
}
.bundle-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 12px;
}
.bundle-btn {
  min-height: 84px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 6px;
  padding: 12px 14px;
  text-align: left;
  font-size: 17px;
}
.bundle-price {
  font-size: 15px;
  opacity: 0.85;
  font-weight: 500;
}
</style>

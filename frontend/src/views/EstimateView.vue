<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Mic, Square, Search, X, Sparkles, LayoutGrid, Keyboard,
  ShoppingCart, Trash2, TriangleAlert,
} from 'lucide-vue-next'
import { api } from '../api.js'
import BottomSheet from '../components/BottomSheet.vue'
import RollingNumber from '../components/RollingNumber.vue'
import SkeletonList from '../components/SkeletonList.vue'
import { flyToCart, haptic, money, toast } from '../composables/ui.js'

// ---------- данные ----------
const router = useRouter()
const priceItems = ref([])
const bundles = ref([])
const loading = ref(true)
const tab = ref('templates') // templates | voice | text
const parseEnabled = ref(false) // фиче-флаг PARSE_ENABLED с сервера
const todayTotal = ref(0)

const itemById = computed(() => Object.fromEntries(priceItems.value.map((i) => [i.id, i])))

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 5) return 'Доброй ночи'
  if (h < 12) return 'Доброе утро'
  if (h < 18) return 'Добрый день'
  return 'Добрый вечер'
})
const todayDate = new Date().toLocaleDateString('ru-RU', {
  day: 'numeric', month: 'long', weekday: 'long',
})

onMounted(async () => {
  try {
    ;[priceItems.value, bundles.value] = await Promise.all([api('/pricelist'), api('/bundles')])
  } finally {
    loading.value = false
  }
  try {
    parseEnabled.value = (await api('/config')).parse_enabled
  } catch {
    parseEnabled.value = false
  }
  // сумма смет, созданных сегодня — в шапку
  try {
    const docs = await api('/documents')
    const today = new Date().toDateString()
    todayTotal.value = docs
      .filter((d) => d.type === 'estimate' && new Date(d.created_at).toDateString() === today)
      .reduce((sum, d) => sum + Number(d.total), 0)
  } catch {
    todayTotal.value = 0
  }
})

// ---------- сжатие шапки при скролле ----------
const compact = ref(false)
const onScroll = () => (compact.value = window.scrollY > 24)
onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))

// ---------- поиск ----------
const search = ref('')
const q = computed(() => search.value.trim().toLowerCase())
const matches = (i) =>
  i.name.toLowerCase().includes(q.value) ||
  (i.synonyms || []).some((s) => s.toLowerCase().includes(q.value))
const filteredItems = computed(() => (q.value ? priceItems.value.filter(matches) : priceItems.value))
const filteredBundles = computed(() =>
  q.value ? sortedBundles.value.filter((b) => b.name.toLowerCase().includes(q.value)) : sortedBundles.value
)

// ---------- корзина сметы (живёт в localStorage до создания документа) ----------
const CART_KEY = 'smeta_cart'
const cart = ref(JSON.parse(localStorage.getItem(CART_KEY) || '[]'))
const cartOpen = ref(false)

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

function addPriceItem(item, qty = 1, event) {
  addToCart(
    { price_item_id: item.id, name: item.name, unit: item.unit, price: item.price },
    qty
  )
  if (qty > 0) {
    haptic()
    flyToCart(event?.currentTarget, `+ ${item.name}`)
  }
}

const cartTotal = computed(() =>
  cart.value.reduce((sum, p) => sum + Number(p.price) * p.qty, 0)
)
const cartCount = computed(() => cart.value.length)
const cartQty = (id) => cart.value.find((p) => p.price_item_id === id)?.qty || 0

function clearCart() {
  cart.value = []
  saveCart()
  cartOpen.value = false
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

function tapBundle(bundle, event) {
  usage.value[bundle.id] = (usage.value[bundle.id] || 0) + 1
  localStorage.setItem(USAGE_KEY, JSON.stringify(usage.value))

  const askParts = bundle.items.filter((p) => p.ask_qty)
  if (askParts.length === 0) return applyBundle(bundle, {}, event)
  askDialog.value = {
    bundle,
    parts: askParts.map((part) => ({
      part,
      item: itemById.value[part.price_item_id],
      qty: part.qty_default,
    })),
  }
}

function applyBundle(bundle, askedQty, event) {
  for (const part of bundle.items) {
    const item = itemById.value[part.price_item_id]
    if (!item) continue
    addToCart(
      { price_item_id: item.id, name: item.name, unit: item.unit, price: item.price },
      askedQty[part.price_item_id] ?? part.qty_default
    )
  }
  haptic()
  flyToCart(event?.currentTarget, `+ ${bundle.name}`)
  askDialog.value = null
}

function confirmAskDialog() {
  const asked = Object.fromEntries(
    askDialog.value.parts.map(({ part, qty }) => [part.price_item_id, Number(qty) || 0])
  )
  applyBundle(askDialog.value.bundle, asked)
}

// ---------- оформление сметы (корзина → PDF-документ) ----------
const checkout = ref(false)
const clientName = ref('')
const creating = ref(false)
const paywall = ref(false) // лимит Free исчерпан

async function goPro() {
  try {
    const { confirmation_url } = await api('/billing/subscribe', { method: 'POST' })
    location.href = confirmation_url
  } catch (e) {
    toast(e.message, 'error')
  }
}

async function createEstimate() {
  creating.value = true
  try {
    const doc = await api('/documents/estimate', {
      method: 'POST',
      body: {
        positions: cart.value.map((p) => ({
          name: p.name,
          unit: p.unit,
          price: String(p.price),
          qty: p.qty,
        })),
        client_name: clientName.value.trim() || null,
      },
    })
    cart.value = []
    saveCart()
    clientName.value = ''
    checkout.value = false
    cartOpen.value = false
    router.push({ path: '/docs', query: { created: doc.id } })
  } catch (e) {
    if (e.status === 402) {
      checkout.value = false
      cartOpen.value = false
      paywall.value = true // корзина сохранена — оформит после апгрейда
    } else {
      toast(e.message, 'error')
    }
  } finally {
    creating.value = false
  }
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
  parsing.value = true
  try {
    review.value = await api('/parse', { method: 'POST', body: { text: dictation.value } })
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    parsing.value = false
  }
}

function removeReviewPosition(index) {
  review.value.positions.splice(index, 1)
}

function addManually() {
  review.value = null
  dictation.value = ''
  tab.value = 'templates'
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
  haptic()
  toast(`Добавлено позиций: ${positions.length}`)
  review.value = null
  dictation.value = ''
  tab.value = 'templates'
}
</script>

<template>
  <div class="screen">
    <!-- Хиро: живой градиент, сжимается при скролле -->
    <header class="hero est-hero" :class="{ compact }">
      <p class="hello">{{ greeting }}</p>
      <div class="today">
        <span class="today-sum">{{ money(todayTotal) }}</span>
        <span class="today-label">сегодня в сметах · {{ todayDate }}</span>
      </div>
    </header>
  
    <!-- Экран проверки распознанного (обязателен перед добавлением) -->
    <template v-if="review">
      <h1>Проверьте распознанное</h1>
      <p class="muted" style="margin-top: -8px">
        Поправьте количество или удалите лишнее — потом «В смету».
      </p>
      <div class="stagger">
        <div v-for="(p, i) in review.positions" :key="p.price_item_id" class="card review-pos">
          <div class="grow">
            <div class="pos-name">{{ p.name }}</div>
            <div class="muted">{{ money(p.price) }} / {{ p.unit }}</div>
          </div>
          <input v-model="p.qty" inputmode="decimal" class="qty-input" :aria-label="`Количество: ${p.name}`" />
          <button class="icon-btn danger" :aria-label="`Убрать ${p.name}`" @click="removeReviewPosition(i)">
            <X :size="19" />
          </button>
        </div>
      </div>
      <div v-if="review.unrecognized.length" class="card unrecognized">
        <TriangleAlert :size="20" aria-hidden="true" />
        <div class="grow">
          <b>Не распознано:</b> {{ review.unrecognized.join(', ') }}
        </div>
        <button class="small secondary" @click="addManually">Добавить вручную</button>
      </div>
      <button class="cta" :disabled="review.positions.length === 0" @click="confirmReview">
        В смету
      </button>
      <button class="ghost" style="margin-top: 8px" @click="review = null">Отмена</button>
    </template>
  
    <template v-else>
      <!-- Поиск сверху -->
      <div class="search-wrap">
        <Search :size="18" class="search-icon" aria-hidden="true" />
        <input
          v-model="search" type="search" placeholder="Найти работу или комплект…"
          aria-label="Поиск по прайсу и комплектам"
        />
      </div>
  
      <!-- Режимы ввода (Голос/Текст — за фиче-флагом PARSE_ENABLED) -->
      <div v-if="parseEnabled" class="segment" role="tablist" aria-label="Режим ввода">
        <button role="tab" :aria-selected="tab === 'templates'" :class="{ active: tab === 'templates' }" @click="tab = 'templates'">
          <LayoutGrid :size="16" /> Шаблоны
        </button>
        <button role="tab" :aria-selected="tab === 'voice'" :class="{ active: tab === 'voice' }" @click="tab = 'voice'">
          <Mic :size="16" /> Голос
        </button>
        <button role="tab" :aria-selected="tab === 'text'" :class="{ active: tab === 'text' }" @click="tab = 'text'">
          <Keyboard :size="16" /> Текст
        </button>
      </div>
  
      <!-- ШАБЛОНЫ -->
      <template v-if="tab === 'templates' || !parseEnabled">
        <SkeletonList v-if="loading" :rows="6" />
        <template v-else>
          <div class="bundle-grid stagger">
            <button
              v-for="bundle in filteredBundles" :key="bundle.id"
              class="bundle-card" @click="tapBundle(bundle, $event)"
            >
              <span class="bundle-name">{{ bundle.name }}</span>
              <span class="bundle-price money">{{ money(bundleSum(bundle)) }}</span>
            </button>
          </div>
  
          <div class="card">
            <div v-for="item in filteredItems" :key="item.id" class="list-item">
              <div class="grow">
                <div>{{ item.name }}</div>
                <div class="muted"><span class="money" style="font-weight:600">{{ money(item.price) }}</span> / {{ item.unit }}</div>
              </div>
              <div class="stepper">
                <button type="button" :aria-label="`Убрать ${item.name}`" @click="addPriceItem(item, -1, $event)">−</button>
                <span class="qty">{{ cartQty(item.id) }}</span>
                <button type="button" :aria-label="`Добавить ${item.name}`" @click="addPriceItem(item, 1, $event)">+</button>
              </div>
            </div>
            <p v-if="!filteredItems.length && !filteredBundles.length" class="muted" style="text-align:center; padding: 12px 0">
              По запросу «{{ search }}» ничего нет
            </p>
          </div>
        </template>
      </template>
  
      <!-- ГОЛОС -->
      <div v-else-if="tab === 'voice'" class="card">
        <template v-if="voiceSupported">
          <button class="cta" :class="{ danger: listening }" @click="toggleVoice">
            <Square v-if="listening" :size="18" style="margin-right: 8px" />
            <Mic v-else :size="18" style="margin-right: 8px" />
            {{ listening ? 'Стоп' : 'Говорите' }}
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
          <Sparkles :size="17" style="margin-right: 8px" />
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
          <Sparkles :size="17" style="margin-right: 8px" />
          {{ parsing ? 'Распознаю…' : 'Распознать позиции' }}
        </button>
      </div>
    </template>
  
    <!-- Стеклянный итог сметы: прилипает над навигацией -->
    <div v-if="cartCount && !review" id="cart-anchor" class="glass cart-bar">
      <button class="cart-open ghost" @click="cartOpen = true" :aria-label="`Открыть смету, позиций: ${cartCount}`">
        <ShoppingCart :size="20" aria-hidden="true" />
        <span class="cart-info">
          <RollingNumber :value="cartTotal" />
          <span class="cart-count">{{ cartCount }} поз.</span>
        </span>
      </button>
      <button class="cart-go" @click="checkout = true">Оформить</button>
    </div>
  
    <!-- Шторка: состав сметы -->
    <BottomSheet :open="cartOpen" title="Смета" @close="cartOpen = false">
      <div v-for="p in cart" :key="p.price_item_id" class="list-item">
        <div class="grow">
          <div>{{ p.name }}</div>
          <div class="muted">{{ money(p.price) }} × {{ p.qty }} {{ p.unit }}</div>
        </div>
        <div class="stepper">
          <button type="button" :aria-label="`Убрать ${p.name}`" @click="addToCart(p, -1)">−</button>
          <span class="qty">{{ p.qty }}</span>
          <button type="button" :aria-label="`Добавить ${p.name}`" @click="addToCart(p, 1)">+</button>
        </div>
      </div>
      <div class="row" style="margin: 14px 0 10px; align-items: center">
        <RollingNumber :value="cartTotal" />
        <button class="small danger" style="flex: none" @click="clearCart">
          <Trash2 :size="16" style="margin-right: 6px" /> Очистить
        </button>
      </div>
      <button class="cta" :disabled="!cartCount" @click="cartOpen = false; checkout = true">
        Оформить смету
      </button>
    </BottomSheet>
  
    <!-- Шторка: «сколько метров?» -->
    <BottomSheet :open="Boolean(askDialog)" :title="askDialog?.bundle.name" @close="askDialog = null">
      <template v-if="askDialog">
        <div v-for="entry in askDialog.parts" :key="entry.part.price_item_id">
          <label>{{ entry.item?.name }} — сколько {{ entry.item?.unit }}?</label>
          <input v-model="entry.qty" inputmode="decimal" />
        </div>
        <button class="cta" style="margin-top: 16px" @click="confirmAskDialog">Добавить</button>
      </template>
    </BottomSheet>
  
    <!-- Шторка: оформление -->
    <BottomSheet :open="checkout" title="Оформить смету" @close="checkout = false">
      <label>Заказчик / объект (попадёт в смету, можно пропустить)</label>
      <input v-model="clientName" placeholder="Сергей, ул. Ленина 5" />
      <div class="row" style="margin: 16px 0; align-items: baseline">
        <span class="muted">Итого</span>
        <RollingNumber :value="cartTotal" style="text-align: right" />
      </div>
      <button class="cta" :disabled="creating" @click="createEstimate">
        {{ creating ? 'Создаю PDF…' : 'Создать смету' }}
      </button>
    </BottomSheet>
  
    <!-- Шторка: пейволл, спокойный, без таймеров -->
    <BottomSheet :open="paywall" title="Создано 3 документа в этом месяце" @close="paywall = false">
      <p class="muted" style="margin: 4px 0 16px">
        На тарифе Free — 3 документа в месяц. Pro снимает лимит и убирает
        водяной знак с PDF — 790 ₽/мес, отмена в любой момент.
        Смета сохранена и никуда не денется.
      </p>
      <button class="cta" @click="goPro">Подключить Pro — 790 ₽/мес</button>
      <button class="ghost" style="margin-top: 8px" @click="paywall = false">
        Вернуться к смете
      </button>
    </BottomSheet>
  </div>
</template>

<style scoped>
/* --- хиро: сжатие и лёгкий блюр при скролле --- */
.est-hero {
  position: sticky; top: 0; z-index: 30;
  transition: padding 220ms var(--ease), border-radius 220ms var(--ease);
}
.est-hero .hello { margin: 0 0 4px; color: var(--on-hero-2); font-size: 15px; }
.est-hero .today { display: flex; flex-direction: column; gap: 2px; }
.est-hero .today-sum {
  font-size: 34px; font-weight: 700; font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
  transition: font-size 220ms var(--ease);
}
.est-hero .today-label { color: var(--on-hero-2); font-size: 13px; }
.est-hero.compact {
  padding-top: 10px; padding-bottom: 12px;
  border-radius: 0 0 18px 18px;
  box-shadow: var(--shadow-float);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
}
.est-hero.compact .today-sum { font-size: 22px; }
.est-hero.compact .hello { display: none; }

/* --- поиск --- */
.search-wrap { position: relative; margin-bottom: var(--s3); }
.search-wrap .search-icon {
  position: absolute; left: 14px; top: 50%; transform: translateY(-50%);
  color: var(--text-3); pointer-events: none;
}
.search-wrap input { padding-left: 42px; border-radius: var(--r); }

/* --- сегмент-контрол режимов --- */
.segment {
  display: flex; gap: 4px; padding: 4px;
  background: var(--surface-2); border-radius: var(--r);
  margin-bottom: var(--s3);
}
.segment button {
  min-height: 40px; font-size: 14px; border-radius: 10px;
  background: transparent; color: var(--text-2);
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
}
.segment button.active { background: var(--surface); color: var(--text); box-shadow: var(--shadow-card); }

/* --- комплекты: карточки с итогом --- */
.bundle-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: var(--s3); margin-bottom: var(--s3);
}
.bundle-card {
  min-height: 86px;
  display: flex; flex-direction: column; align-items: flex-start; justify-content: space-between;
  gap: var(--s2); padding: var(--s3) 14px;
  text-align: left;
  background: var(--surface); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--r);
  box-shadow: var(--shadow-card);
}
.bundle-card:active { background: var(--surface-2); transform: scale(0.98); }
.bundle-name { font-size: 15px; font-weight: 600; line-height: 1.3; }
.bundle-price { color: var(--accent-soft-text); font-size: 15px; }

/* --- проверка распознанного --- */
.review-pos { display: flex; align-items: center; gap: var(--s3); }
.pos-name { font-weight: 600; }
.qty-input { max-width: 84px; text-align: center; font-weight: 700; font-variant-numeric: tabular-nums; }
.unrecognized {
  display: flex; align-items: center; gap: var(--s3);
  background: var(--warning-bg); color: var(--warning);
  border-color: transparent;
}
.unrecognized .grow { color: var(--text); font-size: 14px; }
.unrecognized svg { flex: none; }
.unrecognized button { flex: none; }

/* --- стеклянный итог сметы --- */
.cart-bar {
  position: fixed; z-index: 45;
  left: 50%; transform: translateX(-50%);
  bottom: calc(66px + env(safe-area-inset-bottom));
  width: calc(100% - 2 * var(--s4)); max-width: calc(640px - 2 * var(--s4));
  display: flex; align-items: center; gap: var(--s3);
  padding: 10px 12px;
}
.cart-open {
  flex: 1; display: flex; align-items: center; gap: 10px;
  min-height: 44px; padding: 0 6px; text-align: left;
  color: var(--text);
}
.cart-info { display: flex; flex-direction: column; line-height: 1.2; }
.cart-count { font-size: 12px; color: var(--text-2); font-weight: 600; }
.cart-go { width: auto; min-height: 46px; padding: 0 22px; border-radius: var(--r-s); flex: none; }
</style>

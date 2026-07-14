<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ImagePlus } from 'lucide-vue-next'
import { api, fetchLogoUrl } from '../api.js'
import { toast } from '../composables/ui.js'

const router = useRouter()
const step = ref(1)
const busy = ref(false)

// Шаг 1: профиль
const profile = ref({ brand_name: '', full_name: '', inn: '', requisites: { text: '' } })

// Шаг 2: логотип
const logoUrl = ref(null)

// Шаг 3: прайс
const items = ref([])

onMounted(async () => {
  const p = await api('/profile')
  // не затираем то, что пользователь успел ввести до ответа сервера
  profile.value = {
    brand_name: profile.value.brand_name || p.brand_name || '',
    full_name: profile.value.full_name || p.full_name || '',
    inn: profile.value.inn || p.inn || '',
    requisites: { text: profile.value.requisites.text || p.requisites?.text || '' },
  }
  if (p.has_logo) logoUrl.value = await fetchLogoUrl()
})

async function saveProfile() {
  busy.value = true
  try {
    await api('/profile', { method: 'PUT', body: profile.value })
    step.value = 2
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    busy.value = false
  }
}

async function uploadLogo(event) {
  const file = event.target.files[0]
  if (!file) return
  logoUrl.value = URL.createObjectURL(file) // превью сразу
  const formData = new FormData()
  formData.append('file', file)
  try {
    await api('/profile/logo', { method: 'POST', formData })
  } catch (e) {
    toast(e.message, 'error')
    logoUrl.value = null
  }
}

async function openPriceStep() {
  busy.value = true
  try {
    await api('/pricelist/seed', { method: 'POST' })
    items.value = await api('/pricelist')
    step.value = 3
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    busy.value = false
  }
}

async function savePrice(item) {
  try {
    await api(`/pricelist/${item.id}`, { method: 'PUT', body: { price: String(item.price) } })
  } catch (e) {
    toast(e.message, 'error')
  }
}

function finish() {
  router.push('/new')
}
</script>

<template>
  <div class="screen">
    <div class="steps" aria-label="Шаг онбординга" role="progressbar" :aria-valuenow="step" aria-valuemin="1" aria-valuemax="3">
      <span :class="{ done: step >= 1 }" /><span :class="{ done: step >= 2 }" /><span :class="{ done: step >= 3 }" />
    </div>
  
    <div v-if="step === 1">
      <h1>Ваши данные для документов</h1>
      <div class="card">
        <label>Название бренда (на сметах)</label>
        <input v-model="profile.brand_name" placeholder="КлиматДВ" />
        <label>ФИО</label>
        <input v-model="profile.full_name" placeholder="Иванов Иван Иванович" autocomplete="name" />
        <label>ИНН</label>
        <input v-model="profile.inn" inputmode="numeric" placeholder="272000000000" />
        <label>Реквизиты (банк, счёт — попадут в договор)</label>
        <textarea v-model="profile.requisites.text" placeholder="р/с 40802810…, Банк …, БИК …" />
        <button class="cta" style="margin-top: 16px" :disabled="busy" @click="saveProfile">Дальше</button>
      </div>
    </div>
  
    <div v-else-if="step === 2">
      <h1>Логотип на документы</h1>
      <div class="card">
        <p class="muted" style="margin-top: 0">PNG, JPEG, WebP или SVG до 2 МБ. Можно пропустить и добавить позже.</p>
        <div class="logo-row">
          <div class="logo-circle">
            <img v-if="logoUrl" :src="logoUrl" alt="Логотип" />
            <ImagePlus v-else :size="26" aria-hidden="true" />
          </div>
          <label class="soft replace-btn">
            {{ logoUrl ? 'Заменить' : 'Выбрать файл' }}
            <input
              type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml"
              class="visually-hidden" @change="uploadLogo"
            />
          </label>
        </div>
        <button class="cta" style="margin-top: 16px" :disabled="busy" @click="openPriceStep">Дальше</button>
        <button class="ghost" style="margin-top: 8px" :disabled="busy" @click="openPriceStep">
          Пропустить
        </button>
      </div>
    </div>
  
    <div v-else>
      <h1>Ваш прайс</h1>
      <p class="muted" style="margin-top: -8px">
        Мы заполнили типовой прайс кондиционерщика — поправьте цены под себя.
      </p>
      <div class="card dense">
        <div v-for="item in items" :key="item.id" class="list-item">
          <div class="grow">
            <div>{{ item.name }}</div>
            <div class="muted">₽ / {{ item.unit }}</div>
          </div>
          <input
            v-model="item.price" class="price-input" inputmode="decimal"
            :aria-label="`Цена: ${item.name}`"
            @change="savePrice(item)"
          />
        </div>
      </div>
      <button class="cta" @click="finish">Готово — к работе</button>
    </div>
  </div>
</template>

<style scoped>
.steps { display: flex; gap: 6px; margin: var(--s4) 0; }
.steps span { flex: 1; height: 5px; border-radius: 3px; background: var(--surface-2); transition: background var(--dur); }
.steps span.done { background: var(--accent); }

.price-input { max-width: 120px; text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; }

.logo-row { display: flex; align-items: center; gap: var(--s4); margin: var(--s2) 0; }
.logo-circle {
  width: 84px; height: 84px; border-radius: 50%; flex: none;
  background: var(--surface-2); color: var(--text-3);
  display: flex; align-items: center; justify-content: center;
  overflow: hidden; border: 1px solid var(--border);
}
.logo-circle img { width: 100%; height: 100%; object-fit: cover; }
.replace-btn {
  display: inline-flex; align-items: center; justify-content: center;
  min-height: 44px; padding: 0 20px; margin: 0;
  border-radius: var(--r-s); font-size: 15px; font-weight: 600;
  background: var(--accent-soft); color: var(--accent-soft-text);
  cursor: pointer; width: auto;
}
.visually-hidden {
  position: absolute; width: 1px; height: 1px; min-height: 0;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;
}
</style>

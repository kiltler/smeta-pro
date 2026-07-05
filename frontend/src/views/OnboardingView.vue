<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, fetchLogoUrl } from '../api.js'

const router = useRouter()
const step = ref(1)
const error = ref('')
const busy = ref(false)

// Шаг 1: профиль
const profile = ref({ brand_name: '', full_name: '', inn: '', requisites: { text: '' } })

// Шаг 2: логотип
const logoUrl = ref(null)

// Шаг 3: прайс
const items = ref([])

onMounted(async () => {
  const p = await api('/profile')
  profile.value = {
    brand_name: p.brand_name || '',
    full_name: p.full_name || '',
    inn: p.inn || '',
    requisites: { text: p.requisites?.text || '' },
  }
  if (p.has_logo) logoUrl.value = await fetchLogoUrl()
})

async function saveProfile() {
  error.value = ''
  busy.value = true
  try {
    await api('/profile', { method: 'PUT', body: profile.value })
    step.value = 2
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function uploadLogo(event) {
  const file = event.target.files[0]
  if (!file) return
  error.value = ''
  logoUrl.value = URL.createObjectURL(file) // превью сразу
  const formData = new FormData()
  formData.append('file', file)
  try {
    await api('/profile/logo', { method: 'POST', formData })
  } catch (e) {
    error.value = e.message
    logoUrl.value = null
  }
}

async function openPriceStep() {
  error.value = ''
  busy.value = true
  try {
    await api('/pricelist/seed', { method: 'POST' })
    items.value = await api('/pricelist')
    step.value = 3
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function savePrice(item) {
  try {
    await api(`/pricelist/${item.id}`, { method: 'PUT', body: { price: String(item.price) } })
  } catch (e) {
    error.value = e.message
  }
}

function finish() {
  router.push('/price')
}
</script>

<template>
  <div class="steps">
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
      <p class="error">{{ error }}</p>
      <button :disabled="busy" @click="saveProfile">Дальше</button>
    </div>
  </div>

  <div v-else-if="step === 2">
    <h1>Логотип на документы</h1>
    <div class="card">
      <p class="muted">PNG, JPEG, WebP или SVG до 2 МБ. Можно пропустить и добавить позже.</p>
      <img v-if="logoUrl" :src="logoUrl" class="logo-preview" alt="Логотип" />
      <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" @change="uploadLogo" />
      <p class="error">{{ error }}</p>
      <button :disabled="busy" @click="openPriceStep">Дальше</button>
      <button class="secondary" style="margin-top: 10px" :disabled="busy" @click="openPriceStep">
        Пропустить
      </button>
    </div>
  </div>

  <div v-else>
    <h1>Ваш прайс</h1>
    <p class="muted">Мы заполнили типовой прайс кондиционерщика — поправьте цены под себя.</p>
    <div class="card">
      <div v-for="item in items" :key="item.id" class="list-item">
        <div class="grow">
          <div>{{ item.name }}</div>
          <div class="muted">₽ / {{ item.unit }}</div>
        </div>
        <input
          v-model="item.price" class="price-input" inputmode="numeric"
          @change="savePrice(item)"
        />
      </div>
    </div>
    <p class="error">{{ error }}</p>
    <button @click="finish">Готово — к работе</button>
  </div>
</template>

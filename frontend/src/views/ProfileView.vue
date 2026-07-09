<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, clearToken, fetchLogoUrl } from '../api.js'

const router = useRouter()
const profile = ref({ brand_name: '', full_name: '', inn: '', requisites: { text: '' } })
const logoUrl = ref(null)
const error = ref('')
const saved = ref(false)
const sub = ref(null) // состояние подписки

const fmtDate = (iso) => new Date(iso).toLocaleDateString('ru-RU')

onMounted(async () => {
  const p = await api('/profile')
  profile.value = {
    brand_name: p.brand_name || '',
    full_name: p.full_name || '',
    inn: p.inn || '',
    requisites: { text: p.requisites?.text || '' },
  }
  if (p.has_logo) logoUrl.value = await fetchLogoUrl()
  sub.value = await api('/billing/subscription')
})

async function goPro() {
  error.value = ''
  try {
    const { confirmation_url } = await api('/billing/subscribe', { method: 'POST' })
    location.href = confirmation_url // страница оплаты ЮKassa
  } catch (e) {
    error.value = e.message
  }
}

async function cancelSub() {
  sub.value = await api('/billing/cancel', { method: 'POST' })
}

async function resumeSub() {
  sub.value = await api('/billing/resume', { method: 'POST' })
}

async function save() {
  error.value = ''
  saved.value = false
  try {
    await api('/profile', { method: 'PUT', body: profile.value })
    saved.value = true
    setTimeout(() => (saved.value = false), 2000)
  } catch (e) {
    error.value = e.message
  }
}

async function uploadLogo(event) {
  const file = event.target.files[0]
  if (!file) return
  error.value = ''
  logoUrl.value = URL.createObjectURL(file)
  const formData = new FormData()
  formData.append('file', file)
  try {
    await api('/profile/logo', { method: 'POST', formData })
  } catch (e) {
    error.value = e.message
    logoUrl.value = null
  }
}

function logout() {
  clearToken()
  router.push('/login')
}
</script>

<template>
  <h1>Профиль</h1>

  <!-- Подписка -->
  <div v-if="sub" class="card">
    <h2>Подписка</h2>
    <template v-if="sub.plan === 'pro'">
      <p>
        Тариф <b>Pro</b> — безлимит документов, без водяного знака.
      </p>
      <p v-if="sub.past_due" class="error" style="min-height: 0">
        Не удалось продлить подписку — проверьте карту. Пробуем ещё
        {{ fmtDate(sub.period_end) }} + 3 дня, потом тариф станет Free.
      </p>
      <p v-else-if="sub.cancel_at_period_end" class="muted">
        Продление отключено. Pro работает до {{ fmtDate(sub.period_end) }},
        дальше — Free (данные сохранятся).
      </p>
      <p v-else class="muted">
        Следующее списание {{ sub.price_rub }} ₽ — {{ fmtDate(sub.period_end) }}.
      </p>
      <button v-if="sub.cancel_at_period_end" class="secondary" @click="resumeSub">
        Возобновить продление
      </button>
      <button v-else class="secondary" @click="cancelSub">Отменить подписку</button>
    </template>
    <template v-else>
      <p>
        Тариф <b>Free</b> — использовано
        <b>{{ sub.documents_used }} из {{ sub.documents_limit }}</b>
        документов в этом месяце. На PDF — водяной знак сервиса.
      </p>
      <button @click="goPro">Подключить Pro — {{ sub.price_rub }} ₽/мес</button>
    </template>
  </div>

  <div class="card">
    <label>Название бренда</label>
    <input v-model="profile.brand_name" />
    <label>ФИО</label>
    <input v-model="profile.full_name" />
    <label>ИНН</label>
    <input v-model="profile.inn" inputmode="numeric" />
    <label>Реквизиты</label>
    <textarea v-model="profile.requisites.text" />
    <p class="error">{{ error }}</p>
    <button @click="save">{{ saved ? '✓ Сохранено' : 'Сохранить' }}</button>
  </div>

  <div class="card">
    <h2>Логотип</h2>
    <img v-if="logoUrl" :src="logoUrl" class="logo-preview" alt="Логотип" />
    <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" @change="uploadLogo" />
  </div>

  <button class="danger" @click="logout">Выйти</button>
</template>

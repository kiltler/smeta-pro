<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, clearToken, fetchLogoUrl } from '../api.js'

const router = useRouter()
const profile = ref({ brand_name: '', full_name: '', inn: '', requisites: { text: '' } })
const logoUrl = ref(null)
const error = ref('')
const saved = ref(false)

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

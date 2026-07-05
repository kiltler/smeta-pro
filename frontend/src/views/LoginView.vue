<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api.js'

const router = useRouter()
const step = ref('phone') // phone | code
const phone = ref('')
const code = ref('')
const error = ref('')
const busy = ref(false)

async function requestCode() {
  error.value = ''
  busy.value = true
  try {
    await api('/auth/request-code', { method: 'POST', body: { phone: phone.value } })
    step.value = 'code'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function verify() {
  error.value = ''
  busy.value = true
  try {
    const data = await api('/auth/verify', {
      method: 'POST',
      body: { phone: phone.value, code: code.value },
    })
    setToken(data.access_token)
    // Пустой прайс — значит первый вход: ведём в онбординг
    const items = await api('/pricelist')
    router.push(items.length === 0 ? '/onboarding' : '/price')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <h1>СметаПро</h1>
  <p class="muted">Смета голосом за минуту — PDF с вашим брендом</p>

  <div class="card" v-if="step === 'phone'">
    <label for="phone">Номер телефона</label>
    <input
      id="phone" v-model="phone" type="tel" inputmode="tel"
      placeholder="+7 914 123-45-67" autocomplete="tel"
      @keyup.enter="requestCode"
    />
    <p class="error">{{ error }}</p>
    <button :disabled="busy || !phone" @click="requestCode">Получить код</button>
  </div>

  <div class="card" v-else>
    <label for="code">Код из SMS на {{ phone }}</label>
    <input
      id="code" v-model="code" inputmode="numeric" maxlength="4"
      placeholder="••••" autocomplete="one-time-code"
      @keyup.enter="verify"
    />
    <p class="error">{{ error }}</p>
    <button :disabled="busy || code.length !== 4" @click="verify">Войти</button>
    <button class="secondary" style="margin-top: 10px" @click="step = 'phone'">
      Изменить номер
    </button>
  </div>
</template>
